#!/usr/bin/env node
// Claude Code hook observer for Spectra TDD.  Deliberately observes only: it
// never starts a process, invokes Spectra, or replays a command from a hook.
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const EMPTY = {};
const FORBIDDEN_SHELL = /(?:&&|\|\||;|\||>|<|[\r\n]|`|\$\()/;
const SAFE_SLUG = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const SAFE_ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const SAFE_KEY = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const CASE_NAME_LIMIT = 300;
const TASK_STATUSES = ['proven', 'tested-not-proven', 'failed', 'incomplete'];
const UNRESOLVED_PLACEHOLDER = /<[A-Za-z][A-Za-z0-9 /_.:-]{0,100}>|\{\{[^}\r\n]{1,100}\}\}|\$\{[^}\r\n]{1,100}\}/;
function escapedRegex(value) { return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
const SUPPORTED_FRAMEWORKS = new Set(['vitest', 'jest', 'pytest', 'xunit', 'go', 'rspec', 'cargo']);
const MANDATORY_SECRET_RULES = [
  { pattern: '-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[\\s\\S]*?(?:-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|$)', flags: 'i' },
  { pattern: '\\b(?:AKIA|ASIA)[A-Z0-9]{16}\\b' },
  { pattern: '\\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,255}\\b' },
  { pattern: '\\beyJ[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}\\b' },
  { pattern: "(?im)^\\s*(?:api[_-]?key|secret|token|password|passwd)\\s*[:=]\\s*[\"']?([^\\s\"'#]{12,})" },
];

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${canonical(value[k])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

function argument(name) {
  const i = process.argv.indexOf(name);
  return i >= 0 && i + 1 < process.argv.length ? process.argv[i + 1] : null;
}

function cleanString(value) {
  return typeof value === 'string' ? value : '';
}

function readStdin() {
  try { return fs.readFileSync(0, 'utf8'); } catch { return ''; }
}

function parseJson(text) {
  try {
    const value = JSON.parse(text);
    return value && typeof value === 'object' && !Array.isArray(value) ? value : null;
  } catch { return null; }
}

function validConfig(value) {
  const required = ['schema_version', 'framework', 'commands', 'report_pattern', 'max_failure_summary_chars', 'secret_rules', 'required_report_marker', 'required_summary_heading'];
  if (!value || canonical(Object.keys(value).sort()) !== canonical([...required].sort()) || value.schema_version !== 1 || !SUPPORTED_FRAMEWORKS.has(value.framework) || !Array.isArray(value.commands) || !value.commands.length || !Number.isInteger(value.max_failure_summary_chars) || value.max_failure_summary_chars < 80 || value.max_failure_summary_chars > 2000) return null;
  if (value.report_pattern !== 'openspec/changes/{change_name}/test-evidence.md' || value.required_report_marker !== '<!-- bootstrap-ai-project:tdd-evidence -->' || value.required_summary_heading !== '## TDD 測試摘要') return null;
  const rules = value.secret_rules && typeof value.secret_rules === 'object' && !Array.isArray(value.secret_rules) ? value.secret_rules.rules : value.secret_rules;
  if (!Array.isArray(rules)) return null;
  for (const rule of rules) { if (!rule || typeof rule.id !== 'string' || !regexFor(rule, false)) return null; }
  const ids = new Set();
  for (const item of value.commands) {
    if (!item || canonical(Object.keys(item).sort()) !== canonical(['base', 'id']) || typeof item.id !== 'string' || !SAFE_KEY.test(item.id) || ids.has(item.id) || typeof item.base !== 'string' || !tokensFor(item.base)) return null;
    ids.add(item.id);
  }
  return value;
}

function regexFor(rule, global) {
  let source = typeof rule === 'string' ? rule : rule?.pattern;
  if (typeof source !== 'string') return null;
  let flags = typeof rule === 'object' && typeof rule.flags === 'string' ? rule.flags : '';
  // Secret policies are shared with Python and may use Python's leading
  // inline mode group, e.g. (?im)^password=.  Convert that portable subset.
  const modes = /^\(\?([im]+)\)/.exec(source);
  if (modes) { source = source.slice(modes[0].length); flags += modes[1]; }
  if (global) flags += 'g';
  flags = [...new Set(flags.replace(/[^dgimsuv]/g, ''))].join('');
  try { return new RegExp(source, flags); } catch { return null; }
}

function redact(text, config) {
  let result = cleanString(text);
  const rules = Array.isArray(config.secret_rules) ? config.secret_rules :
    (Array.isArray(config.secret_rules?.rules) ? config.secret_rules.rules : []);
  for (const rule of [...MANDATORY_SECRET_RULES, ...rules]) {
    const expression = regexFor(rule, true);
    if (expression) result = result.replace(expression, '[REDACTED]');
  }
  return result;
}

function bounded(text, config) {
  const max = config.max_failure_summary_chars;
  return redact(cleanString(text), config).trim().slice(0, Math.max(0, max));
}

function eventName(event) {
  return cleanString(event.hook_event_name || event.hookEventName || event.event || event.name);
}

function sessionId(event) {
  const raw = cleanString(event.session_id || event.sessionId || event.conversation_id || event.conversationId || 'default');
  return crypto.createHash('sha256').update(raw).digest('hex').slice(0, 32);
}

function stateFile(config, root, event) {
  const raw = cleanString(event.session_id);
  if (!raw) return null;
  const digest = crypto.createHash('sha256').update(`${raw}\0${root}`).digest('hex');
  return path.join(os.tmpdir(), `bootstrap-ai-project-tdd-observer-${digest}.json`);
}

function loadState(config, root, event) {
  try {
    const file = stateFile(config, root, event);
    if (!file || fs.lstatSync(file).isSymbolicLink()) return null;
    const value = parseJson(fs.readFileSync(file, 'utf8'));
    return value?.schema_version === 1 ? value : null;
  } catch { return null; }
}

function saveState(config, root, event, state) {
  try {
    const file = stateFile(config, root, event);
    if (!file) return;
    // State is intentionally a small, redacted summary rather than hook output.
    const temp = `${file}.tmp`;
    fs.writeFileSync(temp, canonical(state), { encoding: 'utf8', mode: 0o600 });
    fs.renameSync(temp, file);
  } catch { /* A hook must remain non-disruptive when state storage is unavailable. */ }
}

function deleteState(config, root, event) {
  try { const file = stateFile(config, root, event); if (file) fs.unlinkSync(file); } catch { /* already absent */ }
}

function toolInput(event) {
  return event.tool_input && typeof event.tool_input === 'object' ? event.tool_input :
    (event.toolInput && typeof event.toolInput === 'object' ? event.toolInput : {});
}

function commandOf(event) {
  const input = toolInput(event);
  return cleanString(input.command || input.cmd || event.command);
}

function descriptionOf(event) {
  const input = toolInput(event);
  return cleanString(input.description || event.description);
}

function outputOf(event) {
  const strings = value => {
    if (typeof value === 'string') return [value];
    if (!value || typeof value !== 'object' || Array.isArray(value)) return [];
    return ['stdout', 'stderr', 'output', 'message', 'error', 'tool_error'].flatMap(key => typeof value[key] === 'string' ? [value[key]] : []);
  };
  const values = ['tool_response', 'tool_result', 'response', 'error', 'tool_error'].flatMap(key => strings(event[key])).concat(strings(event));
  return [...new Set(values)].join('\n');
}

function wasInterrupted(event) {
  if (event.is_interrupt === true) return true;
  return ['tool_response', 'tool_result', 'response'].some(key =>
    event[key] && typeof event[key] === 'object' && event[key].interrupted === true
  );
}

function postToolFailed(event, output) {
  if (eventName(event) === 'PostToolUseFailure') return true;
  const containers = [event];
  for (const key of ['tool_response', 'tool_result', 'response']) {
    const value = event[key];
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      containers.push(value);
      if (value.metadata && typeof value.metadata === 'object' && !Array.isArray(value.metadata)) containers.push(value.metadata);
    }
  }
  for (const container of containers) {
    const value = container.exit_code ?? container.exitCode;
    if (Number.isInteger(value)) return value !== 0;
  }
  const match = /\b(?:exit(?:ed)?(?:\s+with)?\s+code|exit_code)\s*[:=]?\s*(-?\d+)\b/i.exec(output);
  return Boolean(match && Number(match[1]) !== 0);
}

function parseDescription(description) {
  const match = /^TDD (Red|Green|Refactor): task=([A-Za-z0-9][A-Za-z0-9._-]{0,127}); evidence=([A-Za-z0-9][A-Za-z0-9._-]{0,127})$/.exec(description);
  if (!match || !SAFE_ID.test(match[2]) || !SAFE_KEY.test(match[3])) return { phase: 'unclassified', task_id: null, evidence_key: null };
  return { phase: match[1].toLowerCase(), task_id: match[2], evidence_key: match[3] };
}

function tokensFor(command) {
  if (!command || command.length > 4096 || FORBIDDEN_SHELL.test(command)) return null;
  const tokens = []; let token = ''; let quote = null; let escaped = false;
  for (const char of command.trim()) {
    if (escaped) { token += char; escaped = false; continue; }
    if (char === '\\' && quote !== "'") {
      if (quote === '"') token += char;
      else escaped = true;
      continue;
    }
    if ((char === "'" || char === '"')) { if (!quote) quote = char; else if (quote === char) quote = null; else token += char; continue; }
    if (/\s/.test(char) && !quote) { if (token) { tokens.push(token); token = ''; } continue; }
    token += char;
  }
  if (quote || escaped || token === '' && !tokens.length) return null;
  if (token) tokens.push(token);
  return tokens.length && tokens.every(t => t && t.length <= 512 && !/[`$;&|<>()*?#{}\r\n]/.test(t) && !/%[A-Za-z_][A-Za-z0-9_]*%/.test(t)) ? tokens : null;
}

function safeSelector(token) {
  const normalized = token.replaceAll('\\', '/');
  return token.length <= 512 &&
    !normalized.startsWith('/') &&
    !normalized.startsWith('~') &&
    !/^[A-Za-z]:\//.test(normalized) &&
    !normalized.split('/').includes('..');
}

function allowedCommand(command, config) {
  const tokens = tokensFor(command);
  if (!tokens) return null;
  for (const item of config.commands) {
    const base = tokensFor(item.base);
    if (!base || base.length > tokens.length || base.some((x, i) => x !== tokens[i])) continue;
    const tail = tokens.slice(base.length);
    // Selectors are data, never a second command.  They can include ordinary
    // paths, flags, xUnit's :: form, and quoted paths with spaces.
    if (tail.length <= 16 && tail.every(token => token && !/[`$;&|<>()*?#{}\r\n]/.test(token) && !/%[A-Za-z_][A-Za-z0-9_]*%/.test(token) && safeSelector(token))) return { command_id: item.id, command: command.trim() };
  }
  return null;
}

function safeApplyCommand(command) {
  const tokens = tokensFor(command);
  if (!tokens || tokens.length !== 6 || tokens[0] !== 'spectra' || tokens[1] !== 'instructions' || tokens[2] !== 'apply' || tokens[3] !== '--change' || tokens[5] !== '--json') return null;
  return SAFE_SLUG.test(tokens[4]) ? tokens[4] : null;
}

function numberFrom(pattern, text) {
  const m = pattern.exec(text);
  return m ? Number(m[1]) : 0;
}

function uniqueCases(items, config) {
  return [...new Set(items.map(x => bounded(x.trim(), config)).filter(Boolean))].sort((a, b) => a.localeCompare(b));
}

function parseTestOutput(framework, source) {
  const count = patterns => {
    for (const pattern of patterns) {
      const m = new RegExp(pattern, 'im').exec(source);
      if (m) return [...m.slice(1).map(x => x === undefined ? null : Number(x)), null, null, null, null].slice(0, 4);
    }
    return [null, null, null, null];
  };
  let raw;
  if (framework === 'vitest' || framework === 'jest') {
    const summary = /^\s*Tests:?\s+(.+)$/im.exec(source);
    if (summary) {
      const value = label => {
        const match = new RegExp(`(\\d+)\\s+${label}\\b`, 'i').exec(summary[1]);
        return match ? Number(match[1]) : null;
      };
      let total = value('total');
      if (total === null) {
        const parenthesized = /\((\d+)\)/.exec(summary[1]);
        total = parenthesized ? Number(parenthesized[1]) : null;
      }
      const labeled = [value('passed'), value('failed'), value('skipped'), total];
      if (labeled.slice(0, 3).some(item => item !== null)) raw = labeled;
    }
  }
  if (raw === undefined) {
  switch (framework.toLowerCase()) {
    case 'pytest': {
      const values = ['passed', 'failed', 'skipped'].map(label => { const m = new RegExp(`(\\d+)\\s+${label}\\b`, 'i').exec(source); return m ? Number(m[1]) : null; });
      raw = values.some(x => x !== null) ? [values[0], values[1], values[2], values.filter(x => x !== null).reduce((sum, x) => sum + x, 0)] : [null, null, null, null];
      break;
    }
    case 'xunit': { raw = count(['Failed:\\s*(\\d+),\\s*Passed:\\s*(\\d+),\\s*Skipped:\\s*(\\d+),\\s*Total:\\s*(\\d+)']); raw = raw[0] === null ? raw : [raw[1], raw[0], raw[2], raw[3]]; break; }
    case 'vitest': {
      raw = count(['Tests\\s+(?:(\\d+)\\s+passed)(?:\\s*\\|\\s*(\\d+)\\s+failed)?(?:\\s*\\|\\s*(\\d+)\\s+skipped)?\\s*\\((\\d+)\\)', 'Tests\\s+(?:(\\d+)\\s+failed)\\s*\\|\\s*(\\d+)\\s+passed\\s*\\((\\d+)\\)']);
      if (/Tests\\s+\\d+\\s+failed/i.test(source) && raw[0] !== null) raw = [raw[1], raw[0], null, raw[2]];
      break;
    }
    case 'jest': raw = count(['Tests:\\s*(?:(\\d+)\\s+passed)(?:,\\s*(\\d+)\\s+failed)?(?:,\\s*(\\d+)\\s+skipped)?(?:,\\s*(\\d+)\\s+total)?']); break;
    case 'rspec': { raw = count(['(\\d+)\\s+examples?,\\s*(\\d+)\\s+failures?']); raw = raw[0] === null ? raw : [raw[0] - raw[1], raw[1], null, raw[0]]; break; }
    case 'cargo': { raw = count(['test result:.*?(\\d+)\\s+passed;\\s*(\\d+)\\s+failed;\\s*(\\d+)\\s+ignored']); raw = raw[0] === null ? raw : [raw[0], raw[1], raw[2], raw[0] + raw[1] + raw[2]]; break; }
    case 'go': { const pass = (source.match(/^--- PASS:/gm) || []).length; const fail = (source.match(/^--- FAIL:/gm) || []).length; raw = [pass || null, fail || null, null, pass + fail || null]; break; }
    default: raw = [null, null, null, null];
  }
  }
  const cases = [];
  for (const line of source.split(/\r?\n/)) {
    let m;
    if ((m = /^FAILED\s+([^\s]+)/.exec(line))) cases.push({ name: m[1].trim(), status: 'failed' });
    else if ((m = /^--- (PASS|FAIL):\s+(.+?)(?:\s+\(|$)/.exec(line))) cases.push({ name: m[2].trim(), status: m[1] === 'PASS' ? 'passed' : 'failed' });
    else if ((m = /^\s*[✓✔]\s+(.+)$/.exec(line))) cases.push({ name: m[1].trim(), status: 'passed' });
    else if ((m = /^\s*[×✕]\s+(.+)$/.exec(line))) cases.push({ name: m[1].trim(), status: 'failed' });
    else if ((m = /^\s*\d+\)\s+(.+)$/.exec(line))) cases.push({ name: m[1].trim(), status: 'failed' });
  }
  const limited = cases.filter(x => x.name).map(x => ({
    ...x,
    name: [...x.name].slice(0, CASE_NAME_LIMIT).join(''),
  }));
  const unique = new Map(limited.map(x => [`${x.name}\0${x.status}`, x]));
  return { counts: { passed: raw[0], failed: raw[1], skipped: raw[2], total: raw[3] }, cases: [...unique.values()].sort((a,b) => a.name.localeCompare(b.name) || a.status.localeCompare(b.status)) };
}

function observation(kind, event, details, config) {
  const rawCommand = details.command || '';
  const rawCwd = cleanString(event.cwd || toolInput(event).cwd || '') || details.root;
  const command = redact(rawCommand, config);
  const cwd = redact(rawCwd, config);
  return {
    schema_version: 1, kind, observed: Boolean(details.observed), event: eventName(event),
    phase: details.phase || 'unclassified', task_id: details.task_id ?? null, evidence_key: details.evidence_key ?? null,
    framework: details.framework ?? null, command_id: details.command_id ?? null, command,
    cwd, duration_ms: Number.isInteger(event.duration_ms) && event.duration_ms >= 0 ? event.duration_ms : (Number.isInteger(event.durationMs) && event.durationMs >= 0 ? event.durationMs : null),
    status: details.status || 'unknown', failure_kind: details.failure_kind ?? null,
    counts: details.counts || { passed: null, failed: null, skipped: null, total: null }, cases: details.cases || [],
    failure_summary: details.failure_summary === null ? null : bounded(details.failure_summary || '', config), redacted: command !== rawCommand || cwd !== rawCwd || Boolean(details.redacted), raw_output_stored: false
  };
}

function hookContext(event, value) { return { hookSpecificOutput: { hookEventName: eventName(event), additionalContext: value } }; }
function feedback(event, ob) { return hookContext(event, `TDD_OBSERVATION ${canonical(ob)}`); }

function promptText(event) {
  return cleanString(event.prompt || event.user_prompt || event.userPrompt || event.message || event.text);
}

function testObservation(event, config, root) {
  const name = eventName(event);
  if ((name !== 'PostToolUse' && name !== 'PostToolUseFailure') || ((event.tool_name ?? event.toolName) && (event.tool_name ?? event.toolName) !== 'Bash')) return null;
  const allowed = allowedCommand(commandOf(event), config);
  if (!allowed) return null;
  const classification = parseDescription(descriptionOf(event));
  const raw = outputOf(event); const cleaned = redact(raw, config); const parsed = parseTestOutput(config.framework, cleaned);
  let status = postToolFailed(event, raw) ? 'failed' : 'passed';
  if (wasInterrupted(event) || /\b(interrupted|cancelled|canceled)\b/i.test(cleaned)) status = 'interrupted';
  if (status === 'passed' && parsed.counts.passed !== null && parsed.counts.failed === null) parsed.counts.failed = 0;
  let failure_kind = null;
  if (status !== 'passed') {
    if (/\b(compil(?:e|ation)|build failed|(?:CS|TS)\d{3,5}|error\s+(?:[A-Z]+\d+|\[E\d+\]))/i.test(cleaned)) failure_kind = 'compile';
    else if (/\b(module not found|cannot find module|no module named|missing (?:module|dependency|package)|command not found|not recognized|dependency|configuration error|invalid config(?:uration)?|failed to load config(?:uration)?|permission denied|access denied|setup failed|collection error)/i.test(cleaned)) failure_kind = 'infrastructure';
    else if (/\b(timeout|timed out|time limit|deadline exceeded)/i.test(cleaned)) failure_kind = 'timeout';
    else if (/\b(?:assert(?:ion)?(?:error| failed|[.:])|assert\s+.+?(?:==|!=|===|>=|<=)|expected .* (?:to|but)|but got|mismatch)/i.test(cleaned)) failure_kind = 'assertion';
    else failure_kind = 'unknown';
  }
  return observation('test-observation', event, { observed: true, command: allowed.command, framework: config.framework, command_id: allowed.command_id, ...classification, ...parsed, root: String(root), status, failure_kind, failure_summary: status === 'passed' ? null : cleaned, redacted: cleaned !== raw }, config);
}

function handle(event, config, root, parseOnly) {
  const name = eventName(event);
  if (parseOnly) return testObservation(event, config, root) || EMPTY;
  if (name === 'UserPromptExpansion' || name === 'UserPromptSubmit') {
    let invoked = event.command_name === 'spectra-apply';
    let change = event.command_args ?? event.arguments;
    if (!invoked) {
      const match = /^\s*[$/]spectra-apply(?:\s+([^\s]+))?\s*$/.exec(promptText(event));
      invoked = Boolean(match);
      change = match?.[1] ?? null;
    }
    if (!invoked) return EMPTY;
    if (Array.isArray(change) && change.length === 1) change = change[0];
    change = typeof change === 'string' && SAFE_SLUG.test(change) ? change : null;
    const state = { schema_version: 1, change, observations: [], reminder_sent: false };
    if (!parseOnly) saveState(config, root, event, state);
    return hookContext(event, 'TDD observer initialized; apply Spectra instructions before recording test evidence.');
  }
  if (name === 'PreToolUse') {
    const tool = cleanString(event.tool_name || event.toolName);
    const command = commandOf(event);
    const task = tool === 'Bash' ? safeApplyCommand(command) : null;
    if (!task) return EMPTY;
    const state = loadState(config, root, event) || { schema_version: 1, change: task, observations: [], reminder_sent: false };
    state.change = task;
    if (!parseOnly) saveState(config, root, event, state);
    return EMPTY;
  }
  if (name === 'PostToolUse' || name === 'PostToolUseFailure') {
    const state = loadState(config, root, event);
    const ob = testObservation(event, config, root);
    if (!state || !ob) return EMPTY;
    if (state) {
      const observations = Array.isArray(state.observations) ? state.observations : [];
      state.observations = [...observations, ob];
      saveState(config, root, event, state);
    }
    return feedback(event, ob);
  }
  if (name === 'Stop') {
    const state = loadState(config, root, event);
    if (!state) return EMPTY;
    const missing = [];
    const change = state.change;
    if (!change || !SAFE_SLUG.test(change)) missing.push('a valid Spectra change');
    else {
      let body = ''; try { body = fs.readFileSync(path.join(root, 'openspec', 'changes', change, 'test-evidence.md'), 'utf8'); } catch { body = null; }
      if (body === null) missing.push('test-evidence.md');
      else {
        if (!body.includes(config.required_report_marker)) missing.push('required report marker');
        const visibleBody = body.replace(/<!--[\s\S]*?-->/g, '');
        if (UNRESOLVED_PLACEHOLDER.test(visibleBody)) missing.push('unresolved report placeholders');
        const observations = (state.observations || []).filter(ob => ob && typeof ob === 'object');
        if (observations.length && !body.includes('hook-observed')) missing.push('hook-observed source');
        for (const ob of observations) {
          if (ob.phase === 'unclassified' || typeof ob.evidence_key !== 'string') continue;
          if (!body.includes(`<!-- evidence:${ob.evidence_key} -->`)) missing.push(`evidence:${ob.evidence_key}`);
          if (typeof ob.task_id === 'string') {
            const taskLine = new RegExp(`^.*(?<![A-Za-z0-9._-])${escapedRegex(ob.task_id)}(?![A-Za-z0-9._-]).*(?:${TASK_STATUSES.map(escapedRegex).join('|')}).*$`, 'im');
            if (!taskLine.test(body)) missing.push(`task:${ob.task_id}`);
          }
          if (typeof ob.command_id === 'string' && typeof ob.command === 'string') {
            const phase = `${ob.phase || ''}`.replace(/^./, value => value.toUpperCase());
            const evidenceLine = new RegExp(`^.*(?<![A-Za-z])${escapedRegex(phase)}(?![A-Za-z]).*(?<![A-Za-z0-9._-])${escapedRegex(`${ob.task_id}`)}(?![A-Za-z0-9._-]).*(?<![A-Za-z0-9._-])${escapedRegex(ob.command_id)}(?![A-Za-z0-9._-]).*${escapedRegex(ob.command)}.*hook-observed.*$`, 'im');
            if (!evidenceLine.test(body)) missing.push(`evidence details:${ob.evidence_key}`);
          }
          const relevantCases = (ob.cases || []).filter(item => item && (item.status === 'failed' || item.status === 'skipped') && typeof item.name === 'string');
          if (relevantCases.some(item => !body.includes(item.name) && !body.includes(item.name.replaceAll('\\', '\\\\').replaceAll('|', '\\|')))) missing.push('failed/skipped cases');
        }
      }
    }
    const summary = event.last_assistant_message;
    if (typeof summary !== 'string' || !summary.includes(config.required_summary_heading)) missing.push('required summary heading');
    const taskIds = [...new Set((state.observations || []).filter(ob => ob?.phase !== 'unclassified' && typeof ob?.task_id === 'string').map(ob => ob.task_id))];
    if (typeof summary !== 'string' || taskIds.some(task => !summary.includes(task)) || (taskIds.length && !TASK_STATUSES.some(status => summary.includes(status)))) missing.push('task summary details');
    if (typeof change === 'string' && (typeof summary !== 'string' || !summary.includes(`openspec/changes/${change}/test-evidence.md`))) missing.push('report path');
    if (!missing.length) { if (!parseOnly) deleteState(config, root, event); return EMPTY; }
    const message = [...new Set(missing)].sort().join(', ');
    if (!state.reminder_sent) { if (!parseOnly) { state.reminder_sent = true; saveState(config, root, event, state); } return hookContext(event, `TDD evidence is incomplete: ${message}.`); }
    if (!parseOnly) deleteState(config, root, event);
    return { systemMessage: `TDD evidence remained incomplete; allowing stop. Missing: ${message}.` };
  }
  if (name === 'SessionEnd') {
    if (!parseOnly) deleteState(config, root, event);
    return EMPTY;
  }
  return EMPTY;
}

function main() {
  const configPath = argument('--config');
  const projectRoot = argument('--project-root');
  const parseOnly = process.argv.includes('--parse-only');
  // Invalid input deliberately yields an inert JSON value: no exception text or
  // hook input is echoed to stdout/stderr.
  if (!configPath || !projectRoot) return process.stdout.write('{}\n');
  let config;
  try { config = validConfig(parseJson(fs.readFileSync(path.resolve(configPath), 'utf8'))); } catch { config = null; }
  const event = parseJson(readStdin());
  if (!config || !event) return process.stdout.write('{}\n');
  let result = EMPTY;
  try { result = handle(event, config, fs.realpathSync.native(path.resolve(projectRoot)), parseOnly); } catch { result = EMPTY; }
  process.stdout.write(`${canonical(result)}\n`);
}

main();
