#!/usr/bin/env node
/*
 * Deliberately dependency-free bootstrap planner.  This is also kept free of
 * shell invocations: the paths supplied to it are data, never commands.
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const POLICY = path.resolve(HERE, '..', 'policy');
const ROOT = path.resolve(HERE, '..');
const EXIT = { OK: 0, BLOCK: 2, INVALID: 3, CONFLICT: 4, ARGS: 64, INTERNAL: 1 };

class CliError extends Error { constructor(code, message, details) { super(message); this.code = code; this.details = details; } }
const sha = (v) => crypto.createHash('sha256').update(v).digest('hex');
const stable = (v) => {
  if (Array.isArray(v)) return `[${v.map(stable).join(',')}]`;
  if (v && typeof v === 'object') return `{${Object.keys(v).sort().map(k => `${JSON.stringify(k)}:${stable(v[k])}`).join(',')}}`;
  return JSON.stringify(v);
};
const out = (v) => process.stdout.write(`${stable(v)}\n`);
const readJson = (file) => JSON.parse(fs.readFileSync(file, 'utf8'));
const exists = (p) => { try { fs.lstatSync(p); return true; } catch (e) { if (e.code === 'ENOENT') return false; throw e; } };
const hashFile = (p) => exists(p) ? sha(fs.readFileSync(p)) : null;
const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

function loadPolicy(name) { return readJson(path.join(POLICY, name)); }
const sourcePolicy = loadPolicy('source-inventory.json');
const secretPolicy = loadPolicy('secret-rules.json');
const ignorePolicy = loadPolicy('managed-gitignore.json');
const hookPolicy = loadPolicy('hook-policy.json');
const testPolicy = loadPolicy('test-bootstrap.json');
const testObserverPolicy = loadPolicy('test-observer.json');
const ROLE_IDS = ['implementer', 'test-engineer', 'doc-writer', 'git-commit'];
function loadRoleContracts() {
  const contracts = {};
  const required = ['schema_version', 'id', 'title', 'description', 'trigger', 'capabilities', 'instructions'].sort();
  for (const roleId of ROLE_IDS) {
    const contract = readJson(path.join(ROOT, 'roles', `${roleId}.json`));
    if (!isObject(contract) || stable(Object.keys(contract).sort()) !== stable(required) || contract.schema_version !== 1 || contract.id !== roleId) throw new CliError(EXIT.INTERNAL, 'canonical role contract identity is invalid');
    if (!['title', 'description', 'trigger', 'instructions'].every(key => typeof contract[key] === 'string' && contract[key].trim())) throw new CliError(EXIT.INTERNAL, 'canonical role contract text is invalid');
    if (!isObject(contract.capabilities) || stable(Object.keys(contract.capabilities).sort()) !== stable(['commit', 'run_tests', 'write']) || !Object.values(contract.capabilities).every(value => typeof value === 'boolean')) throw new CliError(EXIT.INTERNAL, 'canonical role capabilities are invalid');
    contracts[roleId] = contract;
  }
  return contracts;
}
const roleContracts = loadRoleContracts();
const policySha256 = sha(stable({ source: sourcePolicy, secret: secretPolicy, gitignore: ignorePolicy, hook: hookPolicy, test: testPolicy, test_observer: testObserverPolicy, roles: roleContracts }));

function args(argv) {
  const [command, ...rest] = argv;
  if (!['discover', 'render-roles', 'plan', 'scan', 'apply', 'verify'].includes(command)) throw new CliError(EXIT.ARGS, 'subcommand must be discover, render-roles, plan, scan, apply, or verify');
  let requestFile, confirm;
  for (let i = 0; i < rest.length; i++) {
    if (rest[i] === '--request' && i + 1 < rest.length) requestFile = rest[++i];
    else if (rest[i] === '--confirm' && i + 1 < rest.length) confirm = rest[++i];
    else throw new CliError(EXIT.ARGS, `unknown or incomplete argument: ${rest[i]}`);
  }
  if (command === 'apply' && !confirm) throw new CliError(EXIT.ARGS, 'apply requires --confirm <plan_sha256>');
  return { command, requestFile, confirm };
}

function getRequest(file) {
  const text = file ? fs.readFileSync(file, 'utf8') : fs.readFileSync(0, 'utf8');
  let v;
  try { v = JSON.parse(text); } catch { throw new CliError(EXIT.INVALID, 'request must be valid JSON'); }
  if (!isObject(v)) throw new CliError(EXIT.INVALID, 'request must be a JSON object');
  return v;
}

function targetPath(value) {
  const raw = typeof value === 'string' ? value : (isObject(value) ? (value.selected_root ?? value.path ?? value.repo_root ?? value.root) : undefined);
  if (typeof raw !== 'string' || !raw) throw new CliError(EXIT.INVALID, 'request.target must identify a directory');
  const p = path.resolve(raw);
  let st;
  try { st = fs.lstatSync(p); } catch { throw new CliError(EXIT.INVALID, 'target directory does not exist'); }
  if (!st.isDirectory() || st.isSymbolicLink()) throw new CliError(EXIT.CONFLICT, 'target must be a real directory, not a symlink');
  return fs.realpathSync.native(p);
}

function relativeSafe(root, rel) {
  if (typeof rel !== 'string' || !rel || path.isAbsolute(rel)) throw new CliError(EXIT.INVALID, 'operation path must be a non-empty relative path');
  const candidate = path.resolve(root, rel);
  if (candidate !== root && !candidate.startsWith(root + path.sep)) throw new CliError(EXIT.CONFLICT, 'operation path escapes target');
  let cur = root;
  for (const part of path.relative(root, candidate).split(path.sep)) {
    if (!part) continue;
    cur = path.join(cur, part);
    if (exists(cur) && fs.lstatSync(cur).isSymbolicLink()) throw new CliError(EXIT.CONFLICT, 'operation path traverses a symlink');
  }
  return candidate;
}

function findRepoRoot(target) {
  let cur = target;
  while (true) {
    if (exists(path.join(cur, '.git'))) return cur;
    const up = path.dirname(cur); if (up === cur) return target; cur = up;
  }
}

function excludedName(name) { return sourcePolicy.excluded_directories.includes(name); }
function privateName(name) {
  if (sourcePolicy.env_key_only_filenames.includes(name)) return false;
  return sourcePolicy.secret_filenames.includes(name) || name === '.env' || name.startsWith('.env.') || sourcePolicy.private_key_suffixes.some(x => name.toLowerCase().endsWith(x));
}
function excludedFile(name) { return sourcePolicy.excluded_suffixes.some(x => name.toLowerCase().endsWith(x)); }
function inventory(root) {
  const files = [], envKeys = {}, evidence = [], manifest = [];
  const walk = (dir) => {
    let entries; try { entries = fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name)); } catch { return; }
    for (const ent of entries) {
      const full = path.join(dir, ent.name), rel = path.relative(root, full).split(path.sep).join('/');
      let stat; try { stat = fs.lstatSync(full); } catch { continue; }
      if (stat.isSymbolicLink()) { manifest.push({ path: rel, kind: 'symlink', included: false, reason: 'symlink' }); continue; }
      if (stat.isDirectory()) {
        if (excludedName(ent.name)) manifest.push({ path: rel, kind: 'directory', included: false, reason: 'excluded-directory' });
        else walk(full);
        continue;
      }
      if (!stat.isFile()) { manifest.push({ path: rel, kind: 'file', bytes: stat.size, included: false, reason: 'not-regular-file' }); continue; }
      const base = { path: rel, kind: 'file', bytes: stat.size };
      if (sourcePolicy.env_key_only_filenames.includes(ent.name)) {
        const keys = [...new Set(fs.readFileSync(full, 'utf8').split(/\r?\n/).map(line => (line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=/) || [])[1]).filter(Boolean))].sort();
        envKeys[rel] = keys;
        manifest.push({ ...base, included: false, reason: 'env-key-only' });
        continue;
      }
      if (privateName(ent.name)) { manifest.push({ ...base, included: false, reason: ent.name.toLowerCase().endsWith('.pem') || ent.name.toLowerCase().endsWith('.key') || ent.name.toLowerCase().endsWith('.p12') || ent.name.toLowerCase().endsWith('.pfx') ? 'private-key-file' : 'secret-file' }); continue; }
      if (stat.size > sourcePolicy.max_file_bytes) { manifest.push({ ...base, included: false, reason: 'too-large' }); continue; }
      if (excludedFile(ent.name)) { manifest.push({ ...base, included: false, reason: 'binary-or-generated' }); continue; }
      const sha256 = sha(fs.readFileSync(full));
      files.push({ path: rel, sha256, bytes: stat.size });
      manifest.push({ ...base, included: true, reason: 'source', sha256 });
    }
  };
  walk(root); files.sort((a, b) => a.path.localeCompare(b.path)); manifest.sort((a, b) => a.path.localeCompare(b.path));
  return { files, envKeys, snapshot: sha(stable(files.map(x => [x.path, x.sha256]))), evidence, manifest };
}

function discover(root) {
  const inv = inventory(root), names = new Set(inv.files.map(x => x.path));
  const stacks = [];
  if ([...names].some(x => path.basename(x) === 'package.json')) stacks.push('node');
  if ([...names].some(x => x.endsWith('.csproj') || x.endsWith('.fsproj') || path.basename(x) === 'global.json')) stacks.push('dotnet');
  if ([...names].some(x => ['pyproject.toml', 'requirements.txt', 'setup.py', 'setup.cfg'].includes(path.basename(x)))) stacks.push('python');
  if (names.has('go.mod')) stacks.push('go'); if (names.has('Cargo.toml')) stacks.push('rust'); if (names.has('Gemfile')) stacks.push('ruby');
  const test_profiles = [];
  const hasTests = inv.files.some(x => x.path.toLowerCase().includes('test'));
  for (const stack of stacks) {
    const framework = testPolicy.frameworks?.[stack]?.framework;
    if (framework) test_profiles.push({ stack, framework, source: hasTests ? 'existing' : 'unavailable' });
  }
  inv.evidence = inv.files.map(file => ({ path: file.path, sha256: file.sha256, bytes: file.bytes }));
  let spectraTdd = null, spectraStatus = 'absent';
  const spectraYaml = inv.files.find(x => x.path === '.spectra.yaml');
  if (spectraYaml) {
    const text = fs.readFileSync(path.join(root, spectraYaml.path), 'utf8');
    const lines = text.split(/\r?\n/).filter(line => /^\s*tdd\s*:/.test(line));
    const match = lines.length === 1 ? lines[0].match(/^\s*tdd\s*:\s*(true|false)\s*(?:#.*)?$/) : null;
    if (lines.length === 0) spectraStatus = 'unset';
    else if (match) {
      spectraTdd = match[1] === 'true';
      spectraStatus = spectraTdd ? 'enabled' : 'disabled';
    } else spectraStatus = 'invalid';
  }
  const environmentExamples = Object.keys(inv.envKeys).sort().map(key => ({ path: key, keys: inv.envKeys[key] }));
  const repo = findRepoRoot(root);
  return {
    schema_version: 2,
    target: { repo_root: repo, selected_root: root, kind: repo === root ? 'single-project' : 'monorepo-target', snapshot_sha256: inv.snapshot },
    discovery: { stacks: stacks.sort(), test_profiles, spectra: { present: names.has('.spectra.yaml'), tdd: spectraTdd, tdd_status: spectraStatus }, openspec: { present: exists(path.join(root, 'openspec')) }, environment_examples: environmentExamples, evidence: inv.evidence.sort((a,b) => a.path.localeCompare(b.path)), source_manifest: inv.manifest },
    decisions: {
      mode: 'docs-only',
      hosts: ['claude', 'codex'],
      roles: Object.fromEntries(ROLE_IDS.map(roleId => [roleId, { surfaces: [] }])),
      git_strategy: 'track',
      spectra_tdd: 'skip',
      dependency_execution: 'not-required'
    },
    derived: {
      spectra_tdd: { requested: false, effective: false },
      test_profile: { source: test_profiles.some(item => item.source === 'existing') ? 'existing' : 'unavailable' },
      commit_patterns_source: 'skill-policy',
      hosts: ['claude', 'codex'],
      tdd_observability: { requested: false, effective: false, observer_runtime: 'unavailable', report_pattern: null }
    },
    operations: [], results: []
  };
}

function canonicalRoleBlock(instructions) {
  return `<!-- bootstrap-ai-project:canonical-role:start -->\n${instructions.trimEnd()}\n<!-- bootstrap-ai-project:canonical-role:end -->\n`;
}
function roleSkillContent(contract, host, marker) {
  const frontmatter = ['---', `name: ${contract.id}`, `description: ${JSON.stringify(contract.description)}`];
  if (host === 'claude') frontmatter.push('disable-model-invocation: true');
  frontmatter.push('---', '');
  return `${frontmatter.join('\n')}<!-- ${marker} -->\n${canonicalRoleBlock(contract.instructions)}`;
}
function codexSkillMetadata(contract, marker) {
  return `# ${marker}\ninterface:\n  display_name: ${JSON.stringify(contract.title)}\n  short_description: ${JSON.stringify(contract.description)}\n  default_prompt: ${JSON.stringify(`使用 $${contract.id} 執行已明確指定的角色工作流。`)}\n\npolicy:\n  allow_implicit_invocation: false\n`;
}
function claudeAgentContent(contract, marker) {
  return `---\nname: ${contract.id}\ndescription: ${JSON.stringify(contract.description)}\n---\n\n<!-- ${marker} -->\n${canonicalRoleBlock(contract.instructions)}`;
}
function codexAgentContent(contract, marker) {
  const instructions = contract.instructions.trimEnd();
  if (instructions.includes("'''")) throw new CliError(EXIT.INTERNAL, 'canonical role instructions cannot contain triple apostrophes');
  return `# ${marker}\nname = ${JSON.stringify(contract.id)}\ndescription = ${JSON.stringify(contract.description)}\ndeveloper_instructions = '''${instructions}\n'''\n`;
}
function renderRoles(root, request) {
  const decisions = request.decisions;
  if (!isObject(decisions)) throw new CliError(EXIT.INVALID, 'request.decisions is required');
  if (!['docs-only', 'full'].includes(decisions.mode)) throw new CliError(EXIT.INVALID, 'decisions.mode must be docs-only or full');
  const hosts = decisions.hosts;
  if (!Array.isArray(hosts) || !hosts.length || hosts.some(host => !['claude', 'codex'].includes(host)) || new Set(hosts).size !== hosts.length) throw new CliError(EXIT.INVALID, 'decisions.hosts must contain unique claude/codex values');
  const normalizedHosts = ['claude', 'codex'].filter(host => hosts.includes(host));
  const roles = decisions.roles;
  if (!isObject(roles) || stable(Object.keys(roles).sort()) !== stable([...ROLE_IDS].sort())) throw new CliError(EXIT.INVALID, 'decisions.roles must define all canonical roles');
  const operations = [], rendered = [];
  for (const roleId of ROLE_IDS) {
    const roleDecision = roles[roleId];
    if (!isObject(roleDecision) || stable(Object.keys(roleDecision)) !== stable(['surfaces'])) throw new CliError(EXIT.INVALID, 'each role decision must contain only surfaces');
    const surfaces = roleDecision.surfaces;
    if (!Array.isArray(surfaces) || surfaces.some(surface => !['skill', 'agent'].includes(surface)) || new Set(surfaces).size !== surfaces.length) throw new CliError(EXIT.INVALID, 'role surfaces must be unique skill/agent values');
    if (decisions.mode === 'docs-only' && surfaces.length) throw new CliError(EXIT.INVALID, 'docs-only mode cannot render roles');
    const contract = roleContracts[roleId];
    for (const surface of ['skill', 'agent']) {
      if (!surfaces.includes(surface)) continue;
      const group = `role:${roleId}:${surface}`, marker = `bootstrap-ai-project:${group}:v1`;
      for (const host of normalizedHosts) {
        const artifacts = [];
        if (surface === 'skill' && host === 'claude') artifacts.push(['skill', `.claude/skills/${roleId}/SKILL.md`, roleSkillContent(contract, host, marker)]);
        else if (surface === 'skill' && host === 'codex') artifacts.push(
          ['skill', `.agents/skills/${roleId}/SKILL.md`, roleSkillContent(contract, host, marker)],
          ['metadata', `.agents/skills/${roleId}/agents/openai.yaml`, codexSkillMetadata(contract, marker)]
        );
        else if (surface === 'agent' && host === 'claude') artifacts.push(['agent', `.claude/agents/${roleId}.md`, claudeAgentContent(contract, marker)]);
        else if (surface === 'agent' && host === 'codex') artifacts.push(['agent', `.codex/agents/${roleId}.toml`, codexAgentContent(contract, marker)]);
        for (const [artifact, targetPath, content] of artifacts) {
          operations.push({ id: `${group}:${host}:${artifact}`, type: 'write', path: targetPath, content, atomic_group: group, managed_marker: marker, host, role: roleId, surface, artifact });
          rendered.push({ role: roleId, surface, host, artifact, path: targetPath, atomic_group: group });
        }
      }
    }
  }
  return { target: root, hosts: normalizedHosts, roles: rendered, operations };
}

function scanText(text, label, exceptions = []) {
  const found = [];
  for (const rule of secretPolicy.rules) {
    // The policy is shared with the Python implementation, whose regex syntax
    // permits leading inline flags such as (?im).  Normalize that small,
    // intentional subset into JavaScript flags before compiling.
    let pattern = rule.pattern, inline = '';
    const inlineMatch = pattern.match(/^\(\?([ims]+)\)/);
    if (inlineMatch) { inline = inlineMatch[1]; pattern = pattern.slice(inlineMatch[0].length); }
    let rx; try { rx = new RegExp(pattern, [...new Set(`${rule.flags || ''}${inline}g`)].filter(x => 'gimsuyd'.includes(x)).join('')); } catch { throw new CliError(EXIT.INTERNAL, `invalid secret policy rule: ${rule.id}`); }
    let match;
    while ((match = rx.exec(text))) {
      const line = text.slice(0, match.index).split('\n').length;
      const exception = rule.allow_exception && exceptions.includes(rule.id);
      found.push({ path: label, rule_id: rule.id, severity: rule.severity, line, blocked: !exception, redacted: rule.redactor || '[REDACTED]' });
      if (match[0].length === 0) rx.lastIndex++;
    }
  }
  return found;
}
function normalizedSecretExceptions(request) {
  const raw = Object.prototype.hasOwnProperty.call(request, 'secret_exceptions')
    ? request.secret_exceptions
    : Object.prototype.hasOwnProperty.call(request, 'exceptions')
      ? request.exceptions
      : [];
  if (!Array.isArray(raw) || !raw.every(item => typeof item === 'string')) throw new CliError(EXIT.INVALID, 'secret_exceptions must be an array of rule ids');
  const allowed = new Set(secretPolicy.rules.filter(rule => rule.allow_exception === true).map(rule => rule.id));
  if (raw.some(item => !allowed.has(item))) throw new CliError(EXIT.INVALID, 'secret_exceptions contains a forbidden rule id');
  return [...new Set(raw)].sort();
}
function scanRequest(request, root) {
  const findings = [], exceptions = normalizedSecretExceptions(request);
  if (Object.prototype.hasOwnProperty.call(request, 'text')) {
    if (typeof request.text !== 'string') throw new CliError(EXIT.INVALID, 'request.text must be a string');
    findings.push(...scanText(request.text, typeof request.path === 'string' ? request.path : '<text>', exceptions));
  }
  if (Object.prototype.hasOwnProperty.call(request, 'texts')) {
    if (!Array.isArray(request.texts)) throw new CliError(EXIT.INVALID, 'request.texts must be an array');
    for (const item of request.texts) {
      if (!isObject(item) || typeof item.path !== 'string' || typeof item.content !== 'string') throw new CliError(EXIT.INVALID, 'each request.texts item requires path and string content');
      findings.push(...scanText(item.content, item.path, exceptions));
    }
  }
  if (Object.prototype.hasOwnProperty.call(request, 'files')) {
    if (!root) throw new CliError(EXIT.INVALID, 'request.target is required when scanning files');
    if (!Array.isArray(request.files) || !request.files.every(item => typeof item === 'string')) throw new CliError(EXIT.INVALID, 'request.files must be an array of relative paths');
    for (const item of request.files) {
      const rel = item;
      const file = relativeSafe(root, rel);
      if (privateName(path.basename(file))) continue;
      let stat; try { stat = fs.lstatSync(file); } catch { throw new CliError(EXIT.INVALID, `scan file does not exist: ${rel}`); }
      if (!stat.isFile()) throw new CliError(EXIT.INVALID, `scan path is not a file: ${rel}`);
      if (stat.size > sourcePolicy.max_file_bytes) throw new CliError(EXIT.INVALID, `scan file exceeds policy size: ${rel}`);
      findings.push(...scanText(fs.readFileSync(file, 'utf8'), path.relative(root, file).split(path.sep).join('/'), exceptions));
    }
  }
  findings.sort((a,b) => a.path.localeCompare(b.path) || a.line - b.line || a.rule_id.localeCompare(b.rule_id));
  return findings;
}

function deepMerge(base, patch, insideEnv = false) {
  if (Array.isArray(base) && Array.isArray(patch)) {
    const result = [...base], have = new Set(base.map(stable)); for (const v of patch) if (!have.has(stable(v))) { have.add(stable(v)); result.push(v); } return result;
  }
  if (isObject(base) && isObject(patch)) {
    const r = { ...base };
    for (const k of Object.keys(patch)) {
      const existing = r[k], incoming = patch[k], preserve = insideEnv && !isObject(existing) && !Array.isArray(existing) && !isObject(incoming) && !Array.isArray(incoming);
      r[k] = k in r ? (preserve ? existing : deepMerge(existing, incoming, insideEnv || k === 'env')) : incoming;
    }
    return r;
  }
  return patch;
}
function validateVariables(value) {
  if (typeof value === 'string') {
    for (const m of value.matchAll(/\$\{([^}]+)\}/g)) if (`${'${'}${m[1]}}` !== hookPolicy.allowed_project_variable) throw new CliError(EXIT.INVALID, 'unsupported variable in hook configuration');
  } else if (Array.isArray(value)) value.forEach(validateVariables);
  else if (isObject(value)) Object.values(value).forEach(validateVariables);
}
function validateHooks(doc, relativePath = undefined) {
  validateVariables(doc);
  if (!isObject(doc) || !Object.prototype.hasOwnProperty.call(doc, 'hooks')) return;
  if (!isObject(doc.hooks)) throw new CliError(EXIT.INVALID, 'hooks must be an object');
  const host = relativePath === '.codex/hooks.json' ? 'codex' : (relativePath === '.claude/settings.json' ? 'claude' : undefined);
  const allowedEvents = new Set(host ? hookPolicy.host_events[host] : [...hookPolicy.matcher_events, ...hookPolicy.matcher_forbidden_events]);
  for (const [event, groups] of Object.entries(doc.hooks)) {
    const forbiddenEvent = hookPolicy.matcher_forbidden_events.includes(event);
    if (!allowedEvents.has(event)) throw new CliError(EXIT.INVALID, `unsupported hook event: ${event}`);
    if (!Array.isArray(groups)) throw new CliError(EXIT.INVALID, `hook groups for ${event} must be an array`);
    for (const group of groups) {
      if (!isObject(group)) throw new CliError(EXIT.INVALID, 'hook group must be an object');
      if (Object.prototype.hasOwnProperty.call(group, 'matcher')) {
        if (typeof group.matcher !== 'string') throw new CliError(EXIT.INVALID, 'hook matcher must be a string');
        if (forbiddenEvent) throw new CliError(EXIT.INVALID, `forbidden hook event may not declare matcher: ${event}`);
      }
      const handlers = Array.isArray(group.hooks) ? group.hooks : [group];
      for (const h of handlers) {
        if (!isObject(h) || !hookPolicy.allowed_handler_types.includes(h.type)) throw new CliError(EXIT.INVALID, 'unsupported hook handler type');
        if (h.type === 'command') {
          if (typeof h.command !== 'string' || !h.command) throw new CliError(EXIT.INVALID, 'command handler requires command');
          if (relativePath === '.codex/hooks.json') {
            if (Object.prototype.hasOwnProperty.call(h, 'args')) throw new CliError(EXIT.INVALID, 'Codex command hooks use one command string, not args');
          } else if (!Array.isArray(h.args) || !h.args.every(x => typeof x === 'string')) throw new CliError(EXIT.INVALID, 'command handler args must be a string array');
        }
      }
    }
  }
}

function validateTestObserverConfig(doc) {
  const required = [
    'commands',
    'framework',
    'max_failure_summary_chars',
    'report_pattern',
    'required_report_marker',
    'required_summary_heading',
    'schema_version',
    'secret_rules'
  ];
  if (!isObject(doc) || stable(Object.keys(doc).sort()) !== stable(required)) throw new CliError(EXIT.INVALID, 'test observer config has unsupported fields');
  if (doc.schema_version !== 1) throw new CliError(EXIT.INVALID, 'unsupported test observer config schema');
  if (!testObserverPolicy.supported_frameworks.includes(doc.framework)) throw new CliError(EXIT.INVALID, 'unsupported test observer framework');
  if (!Array.isArray(doc.commands) || !doc.commands.length || doc.commands.length > 32) throw new CliError(EXIT.INVALID, 'test observer commands must be a non-empty array');
  const ids = new Set();
  for (const item of doc.commands) {
    if (!isObject(item) || stable(Object.keys(item).sort()) !== stable(['base', 'id'])) throw new CliError(EXIT.INVALID, 'invalid test observer command');
    if (
      typeof item.id !== 'string' ||
      !/^[A-Za-z0-9._-]+$/.test(item.id) ||
      item.id.length > 128 ||
      ids.has(item.id) ||
      typeof item.base !== 'string' ||
      !item.base.trim() ||
      item.base.length > 4096 ||
      testObserverPolicy.command_safety.forbidden_fragments.some(fragment => item.base.includes(fragment))
    ) throw new CliError(EXIT.INVALID, 'invalid test observer command');
    ids.add(item.id);
  }
  if (
    doc.report_pattern !== testObserverPolicy.report_pattern ||
    doc.required_report_marker !== testObserverPolicy.required_report_marker ||
    doc.required_summary_heading !== testObserverPolicy.required_summary_heading
  ) throw new CliError(EXIT.INVALID, 'test observer report contract differs from policy');
  if (!Number.isInteger(doc.max_failure_summary_chars) || doc.max_failure_summary_chars < 80 || doc.max_failure_summary_chars > 2000) throw new CliError(EXIT.INVALID, 'invalid test observer summary limit');
  if (stable(doc.secret_rules) !== stable(secretPolicy.rules)) throw new CliError(EXIT.INVALID, 'test observer secret rules must match skill policy');
}

function hookScriptReferences(doc, relativePath = undefined) {
  const references = new Set();
  if (!isObject(doc) || !isObject(doc.hooks)) return [];
  const prefix = `${hookPolicy.allowed_project_variable}/`;
  for (const groups of Object.values(doc.hooks)) {
    if (!Array.isArray(groups)) continue;
    for (const group of groups) {
      if (!isObject(group)) continue;
      const handlers = Array.isArray(group.hooks) ? group.hooks : (Array.isArray(group.handlers) ? group.handlers : []);
      for (const handler of handlers) {
        if (!isObject(handler) || handler.type !== 'command') continue;
        if (relativePath === '.codex/hooks.json') {
          const command = typeof handler.command === 'string' ? handler.command : '';
          const matches = [...command.matchAll(/(?<![A-Za-z0-9_./-])(\.ai\/bootstrap-ai-project\/[A-Za-z0-9_./-]+\.(?:py|mjs|json))(?![A-Za-z0-9_./-])/g)].map(match => match[1]);
          if (command.includes('.ai/bootstrap-ai-project/') && matches.length === 0) throw new CliError(EXIT.INVALID, 'Codex shared hook paths must be unquoted target-relative paths');
          for (const relative of matches) {
            if (relative.split('/').includes('..')) throw new CliError(EXIT.INVALID, 'hook script path is not target-relative');
            references.add(relative);
          }
          continue;
        }
        if (!Array.isArray(handler.args)) continue;
        for (const argument of handler.args) {
          const normalized = argument.replaceAll('\\', '/');
          const runtimeFile = ['.ps1', '.sh', '.py', '.mjs'].some(suffix => normalized.toLowerCase().endsWith(suffix));
          const observerConfig = normalized === `${hookPolicy.allowed_project_variable}/.ai/bootstrap-ai-project/tdd-observer.json`;
          if (!runtimeFile && !observerConfig) continue;
          if (!normalized.startsWith(prefix)) throw new CliError(EXIT.INVALID, 'hook script path must use ${CLAUDE_PROJECT_DIR}');
          const relative = normalized.slice(prefix.length);
          if (!relative || relative.startsWith('/') || relative.split('/').includes('..')) throw new CliError(EXIT.INVALID, 'hook script path is not target-relative');
          references.add(relative);
        }
      }
    }
  }
  return [...references].sort();
}

function managedGitignore(current, strategy) {
  if (!['track', 'ignore'].includes(strategy)) throw new CliError(EXIT.INVALID, 'managed_gitignore strategy must be track or ignore');
  const start = ignorePolicy.start_marker, end = ignorePolicy.end_marker;
  const eol = current.includes('\r\n') ? '\r\n' : '\n';
  const lines = current.length ? current.split(/\r?\n/) : [];
  if (lines.length && lines.at(-1) === '') lines.pop();
  const starts = lines.reduce((a,x,i) => x === start ? [...a,i] : a, []), ends = lines.reduce((a,x,i) => x === end ? [...a,i] : a, []);
  if ((starts.length === 0) !== (ends.length === 0) || starts.length > 1 || ends.length > 1 || (starts.length === 1 && starts[0] > ends[0])) throw new CliError(EXIT.CONFLICT, 'managed .gitignore markers are malformed or ambiguous');
  const block = [start, ...ignorePolicy.strategies[strategy], end];
  let result;
  if (!starts.length) result = [...lines, ...block];
  else result = [...lines.slice(0, starts[0]), ...block, ...lines.slice(ends[0] + 1)];
  return result.join(eol) + eol;
}

function normalizeOperation(op, index) {
  if (!isObject(op)) throw new CliError(EXIT.INVALID, 'each operation must be an object');
  const type = op.type ?? op.kind ?? (['write', 'managed_gitignore', 'merge_json'].includes(op.action) ? op.action : undefined);
  if (!['write', 'managed_gitignore', 'merge_json'].includes(type)) throw new CliError(EXIT.INVALID, 'unsupported operation type');
  return { ...op, type, id: typeof op.id === 'string' && op.id ? op.id : `operation-${index + 1}` };
}
function sortedJson(value) {
  if (Array.isArray(value)) return value.map(sortedJson);
  if (isObject(value)) return Object.fromEntries(Object.keys(value).sort().map(key => [key, sortedJson(value[key])]));
  return value;
}
function validateHookScripts(root, plan, checkExecutable = false) {
  const planned = new Map(plan.map(op => [op._file, op._bytes]));
  const references = new Set();
  for (const op of plan) {
    if (!op.path.endsWith('.json') && op.type !== 'merge_json') continue;
    let document; try { document = JSON.parse(op._bytes.toString('utf8')); } catch { continue; }
    for (const reference of hookScriptReferences(document, op.path)) references.add(reference);
  }
  for (const reference of [...references].sort()) {
    const file = relativeSafe(root, reference);
    let bytes;
    if (planned.has(file)) bytes = planned.get(file);
    else {
      let stat; try { stat = fs.lstatSync(file); } catch { throw new CliError(EXIT.INVALID, `hook script does not exist: ${reference}`); }
      if (!stat.isFile() || stat.isSymbolicLink()) throw new CliError(EXIT.INVALID, `hook script is not a regular file: ${reference}`);
      bytes = fs.readFileSync(file);
    }
    if (reference.toLowerCase().endsWith('.ps1')) {
      if (bytes.length < 3 || bytes[0] !== 0xef || bytes[1] !== 0xbb || bytes[2] !== 0xbf) throw new CliError(EXIT.INVALID, 'PowerShell hook must use UTF-8 BOM');
      const text = bytes.subarray(3).toString('utf8');
      if (hookPolicy.script_validation.powershell.required_tokens.some(token => !text.includes(token))) throw new CliError(EXIT.INVALID, 'PowerShell hook is missing required encoding prologue');
    } else if (reference.toLowerCase().endsWith('.sh')) {
      if ((bytes.length >= 3 && bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf) || !bytes.subarray(0, 2).equals(Buffer.from('#!'))) throw new CliError(EXIT.INVALID, 'POSIX hook requires a BOM-less shebang');
      if (checkExecutable && process.platform !== 'win32' && (fs.statSync(file).mode & 0o111) === 0) throw new CliError(EXIT.INVALID, 'POSIX hook is not executable');
    } else if (reference.toLowerCase().endsWith('.py') || reference.toLowerCase().endsWith('.mjs')) {
      if (bytes.length >= 3 && bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf) throw new CliError(EXIT.INVALID, 'runtime hook script must not use a UTF-8 BOM');
      const decoded = bytes.toString('utf8');
      if (Buffer.from(decoded, 'utf8').compare(bytes) !== 0) throw new CliError(EXIT.INVALID, 'runtime hook script must be valid UTF-8');
    } else if (reference.toLowerCase().endsWith('.json')) {
      let document;
      try { document = JSON.parse(bytes.toString('utf8')); } catch { throw new CliError(EXIT.INVALID, 'hook config must be valid UTF-8 JSON'); }
      if (reference.replaceAll('\\', '/') === '.ai/bootstrap-ai-project/tdd-observer.json') validateTestObserverConfig(document);
    }
  }
}
function buildPlan(root, input) {
  if (!Array.isArray(input.operations)) throw new CliError(EXIT.INVALID, 'plan, apply, and verify requests require operations array');
  const ids = new Set(), paths = new Set(), plan = [];
  for (let i = 0; i < input.operations.length; i++) {
    const op = normalizeOperation(input.operations[i], i); if (ids.has(op.id)) throw new CliError(EXIT.INVALID, 'operation ids must be unique'); ids.add(op.id);
    if (op.atomic_group !== undefined && (typeof op.atomic_group !== 'string' || !op.atomic_group)) throw new CliError(EXIT.INVALID, 'atomic_group must be a non-empty string');
    if (op.managed_marker !== undefined && (typeof op.managed_marker !== 'string' || !op.managed_marker)) throw new CliError(EXIT.INVALID, 'managed_marker must be a non-empty string');
    if (op.host !== undefined && !['claude', 'codex'].includes(op.host)) throw new CliError(EXIT.INVALID, 'operation host must be claude or codex');
    const rel = op.type === 'managed_gitignore' ? (op.path ?? '.gitignore') : op.path;
    if (op.type === 'managed_gitignore' && rel !== '.gitignore') throw new CliError(EXIT.INVALID, 'managed_gitignore may only change target/.gitignore');
    const file = relativeSafe(root, rel), plannedPath = path.relative(root, file).split(path.sep).join('/');
    if (paths.has(plannedPath)) throw new CliError(EXIT.INVALID, 'multiple operations may not write the same path');
    if ([...paths].some(existing => plannedPath.startsWith(existing + '/') || existing.startsWith(plannedPath + '/'))) throw new CliError(EXIT.CONFLICT, 'operation paths may not overlap as ancestor and descendant');
    paths.add(plannedPath);
    const before = hashFile(file);
    let bytes, preview;
    if (op.type === 'write') {
      if (typeof op.content !== 'string') throw new CliError(EXIT.INVALID, 'write requires string content');
      bytes = Buffer.from(op.content, 'utf8'); preview = { bytes: bytes.length, executable: plannedPath.toLowerCase().endsWith('.sh'), type: 'write' };
    } else if (op.type === 'managed_gitignore') {
      let current = ''; if (before !== null) { try { current = fs.readFileSync(file, 'utf8'); } catch { throw new CliError(EXIT.INVALID, '.gitignore must be UTF-8 text'); } }
      bytes = Buffer.from(managedGitignore(current, op.strategy), 'utf8'); preview = { rules: ignorePolicy.strategies[op.strategy].length, strategy: op.strategy, type: 'managed_gitignore' };
    } else {
      if (!isObject(op.patch)) throw new CliError(EXIT.INVALID, 'merge_json requires an object patch');
      let base = {};
      if (before !== null) { try { base = JSON.parse(fs.readFileSync(file, 'utf8')); } catch { throw new CliError(EXIT.INVALID, 'merge_json target contains invalid JSON'); } }
      if (!isObject(base)) throw new CliError(EXIT.INVALID, 'merge_json target must contain a JSON object');
      const merged = deepMerge(base, op.patch);
      bytes = Buffer.from(`${JSON.stringify(sortedJson(merged), null, 2)}\n`, 'utf8'); preview = { bytes: bytes.length, patch_keys: Object.keys(op.patch).sort(), type: 'merge_json' };
    }
    if (plannedPath.endsWith('.json') || op.type === 'merge_json') {
      let document;
      try { document = JSON.parse(bytes.toString('utf8')); } catch { throw new CliError(EXIT.INVALID, 'JSON output must be valid UTF-8 JSON'); }
      validateHooks(document, plannedPath);
      if (plannedPath === '.ai/bootstrap-ai-project/tdd-observer.json') validateTestObserverConfig(document);
    }
    if (op.atomic_group !== undefined) preview.atomic_group = op.atomic_group;
    if (op.host !== undefined) preview.host = op.host;
    for (const key of ['role', 'surface', 'artifact']) {
      if (op[key] !== undefined) {
        if (typeof op[key] !== 'string' || !op[key]) throw new CliError(EXIT.INVALID, `${key} must be a non-empty string`);
        preview[key] = op[key];
      }
    }
    const after = sha(bytes);
    const unmanaged = before !== null && typeof op.managed_marker === 'string' && !fs.readFileSync(file).includes(Buffer.from(op.managed_marker, 'utf8'));
    const action = unmanaged ? 'conflict' : (before === after ? 'skip' : (before === null ? 'create' : 'update'));
    plan.push({ id: op.id, type: op.type, path: plannedPath, before_sha256: before, after_sha256: after, action, preview, ...(op.atomic_group !== undefined ? { atomic_group: op.atomic_group } : {}), ...(op.host !== undefined ? { host: op.host } : {}), _file: file, _bytes: bytes });
  }
  const conflictGroups = new Set(plan.filter(op => op.action === 'conflict' && op.atomic_group).map(op => op.atomic_group));
  for (const op of plan) if (op.atomic_group && conflictGroups.has(op.atomic_group)) op.action = 'conflict';
  validateHookScripts(root, plan);
  const publicOps = plan.map(({ _file, _bytes, ...v }) => v);
  const exceptions = normalizedSecretExceptions(input);
  const payload = { schema_version: 2, target: root, operations: publicOps, secret_exceptions: exceptions, policy_sha256: policySha256 };
  return { plan, publicOps, policy_sha256: policySha256, plan_sha256: sha(stable(payload)) };
}
function publicPlan(root, b) { return { target: root, operations: b.publicOps, policy_sha256: b.policy_sha256, plan_sha256: b.plan_sha256 }; }

function atomicWrite(root, file, bytes) {
  const dir = path.dirname(file); fs.mkdirSync(dir, { recursive: true });
  const realDirectory = fs.realpathSync.native(dir);
  if (relativeSafe(root, path.relative(root, file)) !== file || (realDirectory !== root && !realDirectory.startsWith(root + path.sep))) throw new CliError(EXIT.CONFLICT, 'write path changed or escaped target');
  const tmp = path.join(dir, `.${path.basename(file)}.bootstrap-${process.pid}-${crypto.randomBytes(6).toString('hex')}.tmp`);
  try { fs.writeFileSync(tmp, bytes, { mode: 0o600 }); fs.renameSync(tmp, file); } finally { if (exists(tmp)) fs.unlinkSync(tmp); }
}
function apply(root, request, confirm) {
  const b = buildPlan(root, request);
  if (b.plan_sha256 !== confirm) throw new CliError(EXIT.CONFLICT, 'confirmed plan hash differs from current plan', { plan_sha256: b.plan_sha256 });
  const exceptions = normalizedSecretExceptions(request), blocked = [];
  const writable = b.plan.filter(op => ['create', 'update'].includes(op.action));
  for (const op of writable) blocked.push(...scanText(op._bytes.toString('utf8'), op.path, exceptions));
  if (blocked.some(x => x.blocked)) throw new CliError(EXIT.BLOCK, 'secret policy blocks write', { findings: blocked });
  const committed = [], createdDirectories = new Set();
  for (const op of writable) {
    let cursor = path.dirname(op._file);
    while (cursor !== root && !exists(cursor)) { createdDirectories.add(cursor); cursor = path.dirname(cursor); }
  }
  try {
    for (const op of writable) {
      if (hashFile(op._file) !== op.before_sha256) throw new CliError(EXIT.CONFLICT, `file drifted: ${op.path}`);
      const old = op.before_sha256 === null ? null : fs.readFileSync(op._file);
      atomicWrite(root, op._file, op._bytes);
      if (process.platform !== 'win32' && op.path.toLowerCase().endsWith('.sh')) fs.chmodSync(op._file, fs.statSync(op._file).mode | 0o111);
      committed.push({ ...op, old });
    }
  } catch (err) {
    for (const op of committed.reverse()) {
      try {
        if (hashFile(op._file) !== op.after_sha256) continue;
        if (op.old === null) fs.unlinkSync(op._file); else atomicWrite(root, op._file, op.old);
      } catch { /* Preserve a concurrently changed file rather than overwriting it. */ }
    }
    for (const directory of [...createdDirectories].sort((a, b) => b.split(path.sep).length - a.split(path.sep).length)) {
      try { fs.rmdirSync(directory); } catch { /* Remove only transaction-created directories that remain empty. */ }
    }
    throw err;
  }
  const hasConflicts = b.plan.some(op => op.action === 'conflict');
  const result = { target: root, plan_sha256: b.plan_sha256, policy_sha256: b.policy_sha256, results: b.plan.map(x => ({ operation_id: x.id, status: x.action === 'conflict' ? 'needs-input' : (x.action === 'skip' ? 'skipped' : 'success') })), findings: blocked, blocked: false, ok: !hasConflicts };
  if (hasConflicts) process.exitCode = EXIT.CONFLICT;
  return result;
}
function verify(root, request) {
  const b = buildPlan(root, request), results = [];
  validateHookScripts(root, b.plan, true);
  for (const op of b.plan) {
    if (op.action === 'conflict') {
      results.push({ operation_id: op.id, path: op.path, expected_sha256: op.after_sha256, actual_sha256: op.before_sha256, json_and_hooks_valid: null, status: 'needs-input' });
      continue;
    }
    const actual = hashFile(op._file);
    let structure = null;
    if (op.path.endsWith('.json') || op.type === 'merge_json') {
      try {
        const document = JSON.parse(fs.readFileSync(op._file, 'utf8'));
        validateHooks(document, op.path);
        if (op.path === '.ai/bootstrap-ai-project/tdd-observer.json') validateTestObserverConfig(document);
        structure = true;
      }
      catch { structure = false; }
    }
    const matches = actual === op.after_sha256 && structure !== false;
    results.push({ operation_id: op.id, path: op.path, expected_sha256: op.after_sha256, actual_sha256: actual, json_and_hooks_valid: structure, status: matches ? 'success' : 'failed' });
  }
  const exceptions = normalizedSecretExceptions(request);
  const findings = b.plan.flatMap(op => scanText(op._bytes.toString('utf8'), op.path, exceptions)).sort((a,b) => a.path.localeCompare(b.path) || a.line - b.line || a.rule_id.localeCompare(b.rule_id));
  const bad = results.some(x => x.status === 'failed' || x.status === 'needs-input') || findings.some(x => x.blocked);
  if (bad) process.exitCode = findings.some(x => x.blocked) ? EXIT.BLOCK : EXIT.CONFLICT;
  return { target: root, results, findings, blocked: findings.some(x => x.blocked), ok: !bad };
}

function success(command, payload) { return { schema_version: 2, ok: payload.ok ?? true, command, ...payload }; }

function main() {
  const a = args(process.argv.slice(2)), request = getRequest(a.requestFile);
  if (a.command === 'scan') {
    const root = targetPath(request.target);
    const findings = scanRequest(request, root);
    const blocked = findings.some(x => x.blocked);
    if (blocked) process.exitCode = EXIT.BLOCK;
    return success('scan', { ok: !blocked, ...(root ? { target: root } : {}), findings, blocked });
  }
  const root = targetPath(request.target);
  if (a.command === 'discover') return success('discover', discover(root));
  if (a.command === 'render-roles') return success('render-roles', renderRoles(root, request));
  if (a.command === 'plan') return success('plan', publicPlan(root, buildPlan(root, request)));
  if (a.command === 'apply') return success('apply', apply(root, request, a.confirm));
  return success('verify', verify(root, request));
}
try { out(main()); }
catch (err) {
  const code = err instanceof CliError ? err.code : EXIT.INTERNAL;
  const command = process.argv[2] || null;
  out({ schema_version: 2, ok: false, command, error: { code, message: err instanceof Error ? err.message : 'internal error' }, ...(err?.details ? { details: err.details } : {}) });
  process.exitCode = code;
}
