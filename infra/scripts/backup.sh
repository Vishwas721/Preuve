#!/usr/bin/env bash
# Take a database backup now (Phase 5D). Daily backups happen on their own in the `backup`
# service; this is for "before I change something".
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
compose exec -T backup sh /usr/local/bin/backup-loop.sh once
