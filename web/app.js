const $ = (id) => document.getElementById(id);

const src = $('source');
const hl = $('hl');
const gutter = $('gutter');
const STATEMENTS = new Set(['Program', 'Function', 'Param', 'Block', 'If', 'While', 'DoWhile', 'For',
  'Return', 'Break', 'Continue', 'ExprStmt', 'Cout', 'Cin', 'VarDecl', 'DeclGroup']);
const LEAVES = new Set(['Num', 'Str', 'BoolLit', 'Var', 'Endl']);

let examples = [];
let marked = null;
let errorLine = null;
let root = null;
let selected = null;

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function paintEditor() {
  const lines = src.value.split('\n');
  gutter.textContent = lines.map((_, i) => i + 1).join('\n') + '\n';
  hl.innerHTML = lines.map((line, i) => {
    const n = i + 1;
    const text = escapeHtml(line) || ' ';
    if (n === errorLine) return `<span class="err">${text}</span>`;
    if (n === marked) return `<span class="mark">${text}</span>`;
    return text;
  }).join('\n') + '\n';
  syncScroll();
}

function syncScroll() {
  hl.scrollTop = src.scrollTop;
  hl.scrollLeft = src.scrollLeft;
  gutter.scrollTop = src.scrollTop;
}

function markLine(n) {
  marked = n;
  paintEditor();
  if (!n) return;
  const lineHeight = 20;
  const top = (n - 1) * lineHeight;
  if (top < src.scrollTop || top > src.scrollTop + src.clientHeight - lineHeight * 2) {
    src.scrollTop = Math.max(0, top - src.clientHeight / 3);
    syncScroll();
  }
}

src.addEventListener('input', () => { errorLine = null; marked = null; paintEditor(); });
src.addEventListener('scroll', syncScroll);
src.addEventListener('keydown', (e) => {
  if (e.key === 'Tab') {
    e.preventDefault();
    const { selectionStart: a, selectionEnd: b } = src;
    src.value = src.value.slice(0, a) + '    ' + src.value.slice(b);
    src.selectionStart = src.selectionEnd = a + 4;
    paintEditor();
  }
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    compile();
  }
});

document.querySelectorAll('.tabs button').forEach((btn) => {
  btn.addEventListener('click', () => showTab(btn.dataset.tab));
});

function showTab(name) {
  document.querySelectorAll('.tabs button').forEach((b) => b.classList.toggle('on', b.dataset.tab === name));
  document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('on', t.id === 'tab-' + name));
  if (name === 'tree') fit();
}

async function loadExamples() {
  const res = await fetch('/api/examples');
  examples = await res.json();
  const select = $('example');
  select.innerHTML = examples.map((ex, i) => `<option value="${i}">${ex.name}</option>`).join('');
  const start = examples.findIndex((ex) => ex.name === 'factorial.cpp');
  select.value = String(Math.max(0, start));
  pickExample();
}

function pickExample() {
  const ex = examples[Number($('example').value)];
  if (!ex) return;
  src.value = ex.source;
  $('stdin').value = ex.source.includes('cin') ? '6' : '';
  errorLine = null;
  marked = null;
  paintEditor();
  compile();
}

$('example').addEventListener('change', pickExample);
$('mode').addEventListener('change', compile);
$('go').addEventListener('click', compile);

async function compile() {
  const status = $('status');
  status.textContent = 'транслюю…';
  let data;
  try {
    const res = await fetch('/api/compile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: src.value, stdin: $('stdin').value, mode: $('mode').value }),
    });
    data = await res.json();
  } catch (err) {
    status.innerHTML = `<span class="bad">сервер не відповідає: ${escapeHtml(String(err))}</span>`;
    return;
  }
  render(data);
}

function render(data) {
  const status = $('status');
  const parts = [];
  for (const c of data.conflicts) parts.push(`<span class="warn">yacc: ${escapeHtml(c)}</span>`);
  errorLine = null;
  if (data.errors.length) {
    const e = data.errors[0];
    const stage = e.stage === 'semantic' ? 'семантична помилка' : 'синтаксична помилка';
    const where = e.line ? `рядок ${e.line}${e.col ? ', позиція ' + e.col : ''}: ` : '';
    parts.push(`<span class="bad">${stage}</span> ${where}${escapeHtml(e.message)}`);
    errorLine = e.line;
  } else {
    parts.push('<span class="ok">розбір і семантика без помилок</span>');
  }
  for (const w of data.warnings) parts.push(`<span class="warn">попередження, ${escapeHtml(w)}</span>`);
  status.innerHTML = parts.join('\n');
  paintEditor();

  $('py').innerHTML = data.python ? highlightPython(data.python) : '<span class="help">код не згенеровано</span>';
  renderTokens(data.tokens);
  renderRuns(data);
  if (data.ast) drawTree(data.ast);
}

function highlightPython(code) {
  const re = /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|\b(def|return|if|elif|else|while|for|in|not|and|or|break|continue|pass|import|global|True|False|None|raise|lambda)\b|\b(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b|\b(_idiv|_imod|_out|_read|_fmt|_set|_postinc)\b/g;
  let out = '';
  let last = 0;
  for (const m of code.matchAll(re)) {
    out += escapeHtml(code.slice(last, m.index));
    const cls = m[1] ? 'str' : m[2] ? 'kw' : m[3] ? 'num' : 'help';
    out += `<span class="${cls}">${escapeHtml(m[0])}</span>`;
    last = m.index + m[0].length;
  }
  return out + escapeHtml(code.slice(last));
}

function renderTokens(tokens) {
  $('tok').innerHTML = tokens.map((t) =>
    `<tr data-line="${t.line}"><td>${t.line}:${t.col}</td><td>${t.type}</td><td>${escapeHtml(JSON.stringify(t.value))}</td></tr>`
  ).join('');
  $('tok').querySelectorAll('tr').forEach((tr) => tr.addEventListener('click', () => markLine(Number(tr.dataset.line))));
}

function renderRuns(data) {
  const run = data.run;
  const py = data.python_run;
  $('out-interp').textContent = run ? run.stdout : '';
  $('out-py').textContent = py ? py.stdout : '';
  $('meta-interp').innerHTML = run
    ? (run.error ? `<span class="bad">${escapeHtml(run.error)}</span>` : `main повернула ${run.code} · ${(run.time * 1000).toFixed(1)} мс`)
    : '';
  $('meta-py').innerHTML = py
    ? (py.stderr ? `<span class="bad">${escapeHtml(py.stderr.trim().split('\n').pop())}</span>` : `код виходу ${py.code} · ${(py.time * 1000).toFixed(0)} мс разом із запуском python`)
    : '';
  const same = $('same');
  if (run && py && !run.error && !py.stderr) {
    const ok = run.stdout === py.stdout;
    same.className = 'same ' + (ok ? 'yes' : 'no');
    same.textContent = ok ? 'виводи збігаються' : 'виводи різні';
  } else {
    same.className = 'same';
    same.textContent = '';
  }
}

const svg = d3.select('#tree');
const scene = svg.append('g');
const linkLayer = scene.append('g');
const nodeLayer = scene.append('g');
const zoom = d3.zoom().scaleExtent([0.15, 3]).on('zoom', (e) => scene.attr('transform', e.transform));
svg.call(zoom).on('dblclick.zoom', null);
const tip = $('tip');

function kind(d) {
  if (STATEMENTS.has(d.data.type)) return 'stmt';
  if (LEAVES.has(d.data.type)) return 'leaf';
  return 'expr';
}

function drawTree(ast) {
  root = d3.hierarchy(ast, (d) => d.children);
  root.each((d) => { d.id = d.ancestors().map((a) => a.parent ? a.parent.children.indexOf(a) : 0).join('.'); });
  selected = null;
  update();
  fit();
}

function toggle(d) {
  if (d.children) {
    d._children = d.children;
    d.children = null;
  } else if (d._children) {
    d.children = d._children;
    d._children = null;
  }
}

function update() {
  const layout = d3.tree().nodeSize([34, 175]).separation((a, b) => (a.parent === b.parent ? 1 : 1.3));
  layout(root);
  const nodes = root.descendants();
  const links = root.links();

  linkLayer.selectAll('path').data(links, (d) => d.target.id).join('path')
    .attr('class', 'link')
    .attr('d', d3.linkHorizontal().x((d) => d.y).y((d) => d.x));

  const node = nodeLayer.selectAll('g.node').data(nodes, (d) => d.id).join((enter) => {
    const g = enter.append('g');
    g.append('circle').attr('r', 5.5);
    g.append('text').attr('class', 'role').attr('x', 10).attr('y', -9);
    g.append('text').attr('class', 'label').attr('x', 10).attr('dy', '0.35em');
    return g;
  });

  node.attr('class', (d) => `node ${kind(d)}${d._children ? ' folded' : ''}${d === selected ? ' sel' : ''}`)
    .attr('transform', (d) => `translate(${d.y},${d.x})`);
  node.select('.role').text((d) => d.data.role || '');
  node.select('.label').text((d) => d.data.label);

  node.on('click', (event, d) => {
    if (selected === d && (d.children || d._children)) toggle(d);
    selected = d;
    markLine(d.data.line);
    update();
  });
  node.on('mouseenter', (event, d) => {
    const bits = [d.data.type];
    if (d.data.ctype) bits.push('тип ' + d.data.ctype);
    if (d.data.line) bits.push('рядок ' + d.data.line);
    tip.textContent = bits.join(' · ');
    tip.style.opacity = 1;
  });
  node.on('mousemove', (event) => {
    const box = $('tab-tree').getBoundingClientRect();
    tip.style.left = (event.clientX - box.left + 14) + 'px';
    tip.style.top = (event.clientY - box.top + 14) + 'px';
  });
  node.on('mouseleave', () => { tip.style.opacity = 0; });
}

function fit() {
  if (!root) return;
  const el = svg.node();
  const w = el.clientWidth;
  const h = el.clientHeight;
  if (!w || !h) return;
  const nodes = root.descendants();
  const xs = nodes.map((d) => d.x);
  const ys = nodes.map((d) => d.y);
  const minX = Math.min(...xs) - 30;
  const maxX = Math.max(...xs) + 30;
  const minY = Math.min(...ys) - 20;
  const maxY = Math.max(...ys) + 170;
  const k = Math.min(1.2, w / (maxY - minY), h / (maxX - minX));
  const tx = (w - (maxY - minY) * k) / 2 - minY * k;
  const ty = (h - (maxX - minX) * k) / 2 - minX * k;
  svg.call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(k));
}

$('fit').addEventListener('click', fit);
$('expand').addEventListener('click', () => {
  if (!root) return;
  const open = (d) => {
    if (d._children) { d.children = d._children; d._children = null; }
    (d.children || []).forEach(open);
  };
  open(root);
  update();
  fit();
});

window.addEventListener('resize', fit);
loadExamples();
