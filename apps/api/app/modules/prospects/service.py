import uuid
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analysis.models import ICP, ICPStatus
from app.modules.prospects import scoring
from app.modules.prospects.models import Company, CompanyEvidence, Contact, LeadScore
from app.modules.prospects.schemas import ProspectUpdate, ResearchCompanyInput
from app.modules.research.pack import name_key


class ProspectError(Exception):
    pass


# ---------- ICP resolution ----------


async def primary_icp_id(session: AsyncSession, idea_id: uuid.UUID) -> uuid.UUID | None:
    return await session.scalar(
        select(ICP.id).where(ICP.idea_id == idea_id, ICP.is_primary, ICP.status == ICPStatus.ACTIVE)
    )


def _icp_target(icp: ICP | None) -> scoring.ICPTarget | None:
    if icp is None:
        return None
    return scoring.ICPTarget(
        name=icp.name,
        size_min=icp.size_min,
        size_max=icp.size_max,
        user_roles=tuple(icp.roles.get("users", [])),
        buyer_roles=tuple(icp.roles.get("buyers", [])),
    )


# ---------- research merge ----------


async def upsert_from_research(
    session: AsyncSession,
    idea_id: uuid.UUID,
    import_id: uuid.UUID,
    items: list[ResearchCompanyInput],
) -> dict[str, Any]:
    """Merge verified companies by domain and contacts by name (does not commit), then score.

    The user's status choice is kept; research facts are refreshed.
    """
    default_icp = await primary_icp_id(session, idea_id)
    created, updated, contacts_added = [], [], 0
    touched: list[Company] = []
    for item in items:
        company = await session.scalar(
            select(Company).where(Company.idea_id == idea_id, Company.domain == item.domain)
        )
        fields = {
            "name": item.name,
            "website": item.website,
            "location": item.location,
            "industry": item.industry,
            "description": item.description,
            "size_min": item.size_min,
            "size_max": item.size_max,
            "size_signal": item.size_signal,
            "size_evidence_id": item.size_evidence_id,
            "in_geo": item.in_geo,
            "geo_evidence_id": item.geo_evidence_id,
            "technologies": item.technologies,
            "assessments": item.assessments,
        }
        if company is None:
            company = Company(
                idea_id=idea_id, domain=item.domain, icp_id=item.icp_id or default_icp, **fields
            )
            session.add(company)
            created.append(item.name)
        else:
            for k, v in fields.items():
                setattr(company, k, v)
            if item.icp_id:
                company.icp_id = item.icp_id
            updated.append(company.name)
        company.last_import_id = import_id
        await session.flush()

        linked = set(
            await session.scalars(
                select(CompanyEvidence.evidence_id).where(CompanyEvidence.company_id == company.id)
            )
        )
        for eid in dict.fromkeys(item.evidence_ids):
            if eid not in linked:
                session.add(CompanyEvidence(company_id=company.id, evidence_id=eid))

        for c in item.contacts:
            key = name_key(c.name)
            contact = await session.scalar(
                select(Contact).where(Contact.company_id == company.id, Contact.name_key == key)
            )
            if contact is None:
                contact = Contact(company_id=company.id, name_key=key)
                session.add(contact)
                contacts_added += 1
            contact.name, contact.role = c.name, c.role
            contact.email = c.email or contact.email
            contact.evidence_id, contact.source_url = c.evidence_id, c.source_url
            contact.collected_at = datetime.now(UTC)
        await session.flush()
        touched.append(company)

    for company in touched:
        await rescore_company(session, company)
    return {"created": created, "updated": updated, "contacts_added": contacts_added}


# ---------- scoring ----------


async def _evidence_ids(session: AsyncSession, company_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        await session.scalars(
            select(CompanyEvidence.evidence_id).where(CompanyEvidence.company_id == company_id)
        )
    )


def _assessment(data: dict | None) -> scoring.AssessmentInput | None:
    if not data:
        return None
    return scoring.AssessmentInput(
        rating=data["rating"],
        rationale=data["rationale"],
        evidence_ids=tuple(sorted(data.get("evidence_ids", []))),
    )


async def rescore_company(session: AsyncSession, company: Company) -> LeadScore:
    """Compute the score from stored data; append a row only if the inputs changed."""
    # Lazy import: research.service imports this module to merge companies.
    from app.modules.research import service as research

    evidence_ids = await _evidence_ids(session, company.id)
    labels = await research.evidence_labels(session, evidence_ids)
    roles = tuple(
        sorted(await session.scalars(select(Contact.role).where(Contact.company_id == company.id)))
    )
    icp = await session.get(ICP, company.icp_id) if company.icp_id else None

    inp = scoring.ScoringInput(
        company_fit=_assessment(company.assessments.get("company_fit")),
        technology_fit=_assessment(company.assessments.get("technology_fit")),
        other_signals=_assessment(company.assessments.get("other_signals")),
        linked_evidence=tuple(
            sorted(
                (scoring.LinkedEvidence(str(eid), *labels[eid]) for eid in labels),
                key=lambda e: e.id,
            )
        ),
        contact_roles=roles,
        size_min=company.size_min,
        size_max=company.size_max,
        size_signal=company.size_signal,
        size_evidence_id=str(company.size_evidence_id) if company.size_evidence_id else None,
        in_geo=company.in_geo,
        geo_evidence_id=str(company.geo_evidence_id) if company.geo_evidence_id else None,
        icp=_icp_target(icp),
    )
    result = scoring.score(inp)

    latest = await _latest_score(session, company.id)
    if latest is not None and latest.inputs_hash == result.inputs_hash:
        return latest
    row = LeadScore(
        # Python timestamp: Postgres now() is constant within a transaction, which would tie
        # several scores written in one transaction.
        created_at=datetime.now(UTC),
        company_id=company.id,
        icp_id=company.icp_id,
        total=result.total,
        components=[asdict(c) for c in result.components],
        inputs_hash=result.inputs_hash,
    )
    session.add(row)
    await session.flush()
    return row


async def rescore_idea(session: AsyncSession, idea_id: uuid.UUID) -> int:
    companies = list(await session.scalars(select(Company).where(Company.idea_id == idea_id)))
    for company in companies:
        await rescore_company(session, company)
    await session.commit()
    return len(companies)


async def _latest_score(session: AsyncSession, company_id: uuid.UUID) -> LeadScore | None:
    return await session.scalar(
        select(LeadScore)
        .where(LeadScore.company_id == company_id)
        .order_by(LeadScore.created_at.desc())
        .limit(1)
    )


# ---------- reading ----------


async def list_prospects(
    session: AsyncSession,
    idea_id: uuid.UUID,
    *,
    status: str | None = None,
    min_score: int | None = None,
) -> list[dict[str, Any]]:
    query = select(Company).where(Company.idea_id == idea_id)
    if status:
        query = query.where(Company.status == status)
    companies = list(await session.scalars(query))
    ids = [c.id for c in companies]

    scores: dict[uuid.UUID, int] = {}
    contacts: dict[uuid.UUID, list[Contact]] = defaultdict(list)
    if ids:
        latest = (
            select(LeadScore.company_id, func.max(LeadScore.created_at).label("at"))
            .where(LeadScore.company_id.in_(ids))
            .group_by(LeadScore.company_id)
            .subquery()
        )
        for cid, total in await session.execute(
            select(LeadScore.company_id, LeadScore.total).join(
                latest,
                (LeadScore.company_id == latest.c.company_id)
                & (LeadScore.created_at == latest.c.at),
            )
        ):
            scores[cid] = total
        for contact in await session.scalars(select(Contact).where(Contact.company_id.in_(ids))):
            contacts[contact.company_id].append(contact)

    rows = []
    for c in companies:
        total = scores.get(c.id)
        if min_score is not None and (total is None or total < min_score):
            continue
        rows.append(
            {
                "id": c.id,
                "name": c.name,
                "website": c.website,
                "domain": c.domain,
                "location": c.location,
                "industry": c.industry,
                "status": c.status,
                "icp_id": c.icp_id,
                "score": total,
                "contacts": len(contacts[c.id]),
                "top_contact_role": contacts[c.id][0].role if contacts[c.id] else None,
            }
        )
    return sorted(rows, key=lambda r: (-(r["score"] or -1), r["name"]))


async def get_company(
    session: AsyncSession, idea_id: uuid.UUID, company_id: uuid.UUID
) -> Company | None:
    return await session.scalar(
        select(Company).where(Company.id == company_id, Company.idea_id == idea_id)
    )


async def prospect_detail(session: AsyncSession, company: Company) -> dict[str, Any]:
    [summary] = [r for r in await list_prospects(session, company.idea_id) if r["id"] == company.id]
    contact_rows = list(
        await session.scalars(
            select(Contact).where(Contact.company_id == company.id).order_by(Contact.name)
        )
    )
    latest = await _latest_score(session, company.id)
    return summary | {
        "description": company.description,
        "size_min": company.size_min,
        "size_max": company.size_max,
        "size_signal": company.size_signal,
        "in_geo": company.in_geo,
        "technologies": company.technologies,
        "evidence_ids": await _evidence_ids(session, company.id),
        "contacts_list": contact_rows,
        "components": latest.components if latest else [],
        "scored_at": latest.created_at if latest else None,
        "inputs_hash": latest.inputs_hash if latest else None,
    }


async def company_evidence_ids(session: AsyncSession, company_id: uuid.UUID) -> list[uuid.UUID]:
    return await _evidence_ids(session, company_id)


async def latest_score_total(session: AsyncSession, company_id: uuid.UUID) -> int | None:
    latest = await _latest_score(session, company_id)
    return latest.total if latest else None


async def get_contact(
    session: AsyncSession, idea_id: uuid.UUID, contact_id: uuid.UUID
) -> tuple[Contact, Company] | None:
    row = (
        await session.execute(
            select(Contact, Company)
            .join(Company, Company.id == Contact.company_id)
            .where(Contact.id == contact_id, Company.idea_id == idea_id)
        )
    ).first()
    return (row[0], row[1]) if row else None


async def list_idea_contacts(
    session: AsyncSession, idea_id: uuid.UUID
) -> list[tuple[Contact, Company]]:
    rows = await session.execute(
        select(Contact, Company)
        .join(Company, Company.id == Contact.company_id)
        .where(Company.idea_id == idea_id)
        .order_by(Company.name, Contact.name)
    )
    return [(c, co) for c, co in rows]


# ---------- updates ----------


async def update_prospect(session: AsyncSession, company: Company, data: ProspectUpdate) -> None:
    changes = data.model_dump(exclude_unset=True)
    if "icp_id" in changes and changes["icp_id"] is not None:
        icp = await session.get(ICP, changes["icp_id"])
        if icp is None or icp.idea_id != company.idea_id:
            raise ProspectError("ICP not found on this idea")
    for k, v in changes.items():
        setattr(company, k, v)
    if "icp_id" in changes:
        await rescore_company(session, company)
    await session.commit()


async def delete_contact(session: AsyncSession, idea_id: uuid.UUID, contact_id: uuid.UUID) -> bool:
    """Hard-delete a person's data (PRD §37): suppress their address, drop or redact messages."""
    # Lazy import: outreach.service imports this module.
    from app.modules.outreach import service as outreach

    contact = await session.scalar(
        select(Contact)
        .join(Company, Company.id == Contact.company_id)
        .where(Contact.id == contact_id, Company.idea_id == idea_id)
    )
    if contact is None:
        return False
    company = await session.get(Company, contact.company_id)
    await outreach.forget_contact(session, contact.id, contact.email)
    await session.execute(delete(Contact).where(Contact.id == contact_id))
    await rescore_company(session, company)
    await session.commit()
    return True
