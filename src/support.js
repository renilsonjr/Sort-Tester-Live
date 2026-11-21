// Support tickets: the client half of /api/ranked/support (issue #26).
//
// Only a player request creates a ticket, so nothing here runs on its own:
// every call below happens because somebody pressed something.
//
// The server decides what a player may see. This module never filters a
// list to hide another player's case, because it is never sent one.

const API_BASE = (typeof window !== 'undefined' && window.SORT_TESTER_API_BASE)
  ? window.SORT_TESTER_API_BASE
  : '/api';

async function api(method, path, body) {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
  };
  if (body !== undefined) options.body = JSON.stringify(body);
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, options);
  } catch {
    // The screens treat a not-ok answer as "could not load". An unreachable
    // server is that, not a crash: status 0 says no answer came back.
    return { ok: false, status: 0, data: null };
  }
  const data = response.headers.get('content-type')?.includes('application/json')
    ? await response.json().catch(() => null)
    : null;
  return { ok: response.ok, status: response.status, data };
}

export async function listTickets() {
  return api('GET', '/ranked/support/tickets');
}

export async function createTicket(attemptId, description) {
  const body = { attempt_id: attemptId };
  // An empty box is no description, not an empty one.
  const text = (description ?? '').trim();
  if (text) body.description = text;
  return api('POST', '/ranked/support/tickets', body);
}

export async function readTicket(ticketId) {
  return api('GET', `/ranked/support/tickets/${ticketId}`);
}

// What a closed ticket says about its evidence: either the date it goes, or
// that an open linked case is holding it. Never which case, never whose.
export function retentionLine(ticket, formatDate = (iso) => iso) {
  if (!ticket.closed_at) {
    return 'Your evidence is kept while this case is open.';
  }
  if (ticket.evidence_held_by_open_case) {
    return 'Kept for now: this connection log is shared with another case that is still open.';
  }
  if (ticket.evidence_deleted_at) {
    return `Description and connection details are deleted on ${formatDate(ticket.evidence_deleted_at)}.`;
  }
  return 'Description and connection details are deleted 15 days after closure.';
}

export function outcomeLabel(ticket) {
  if (!ticket.closed_at) return 'Open';
  if (ticket.outcome === 'network_instability') return 'Closed · network instability';
  if (ticket.outcome === 'insufficient_evidence') return 'Closed · not enough evidence';
  return 'Closed';
}
