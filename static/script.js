/* ─── State ──────────────────────────────────────────────── */
let threadId    = null;
let isLoading   = false;
let chatStarted = false;

/* ─── DOM refs ───────────────────────────────────────────── */
const app         = document.getElementById('app');
const chat        = document.getElementById('chat');
const messages    = document.getElementById('messages');
const inputEl     = document.getElementById('input');
const sendBtn     = document.getElementById('sendBtn');
const newTripBtn  = document.getElementById('newTripBtn');
const inputBar    = document.getElementById('inputBar');
const contentArea = document.getElementById('contentArea');

/* ─── marked.js config ───────────────────────────────────── */
if (typeof marked !== 'undefined') {
  marked.setOptions({ breaks: true, gfm: true });
}

/* ─── Center the input bar in the content area ───────────── */
function centerInput() {
  if (chatStarted) return;
  const contentH = contentArea.offsetHeight;
  const inputH   = inputBar.offsetHeight;
  const offset = -Math.round((contentH - inputH) / 2);
  inputBar.style.transform = `translateY(${offset}px)`;
  chat.style.paddingBottom = (inputH + 16) + 'px';
}

window.addEventListener('DOMContentLoaded', centerInput);
window.addEventListener('resize', () => { if (!chatStarted) centerInput(); });

/* ─── Suggestion pills ───────────────────────────────────── */
function fillInput(text) {
  inputEl.value = text;
  grow(inputEl);
  inputEl.focus();
}

/* ─── Textarea auto-grow ─────────────────────────────────── */
function grow(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 150) + 'px';
}

/* ─── Keyboard handler ───────────────────────────────────── */
function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    send();
  }
}

/* ─── Send message ───────────────────────────────────────── */
function send() {
  const text = inputEl.value.trim();
  if (!text || isLoading) return;

  if (!chatStarted) startChat();

  appendUserMessage(text);
  inputEl.value = '';
  grow(inputEl);

  isLoading = true;
  sendBtn.disabled = true;

  const typingId = appendTyping();

  fetch('/api/travel', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: text, thread_id: threadId }),
  })
    .then(r => r.json())
    .then(data => {
      removeTyping(typingId);
      isLoading = false;
      sendBtn.disabled = false;

      if (data.success) {
        threadId = data.thread_id;
        appendBotMessage(data);
      } else {
        appendError(data.error || 'Something went wrong. Please try again.');
      }
    })
    .catch(_err => {
      removeTyping(typingId);
      isLoading = false;
      sendBtn.disabled = false;
      appendError('Could not reach the server. Is it running?');
    });
}

/* ─── Transition: input slides to bottom, hero fades out ─── */
function startChat() {
  chatStarted = true;
  app.classList.add('active');
  inputBar.style.transform = 'translateY(0)';
  newTripBtn.style.display = 'flex';
}

/* ─── New trip: reset and re-center the input ────────────── */
function newTrip() {
  threadId    = null;
  isLoading   = false;
  chatStarted = false;
  messages.innerHTML = '';
  app.classList.remove('active');
  newTripBtn.style.display = 'none';
  inputEl.value = '';
  grow(inputEl);
  inputEl.focus();
  requestAnimationFrame(centerInput);
}

/* ─── Append user bubble ─────────────────────────────────── */
function appendUserMessage(text) {
  const div = document.createElement('div');
  div.className = 'message user-message';
  div.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
  messages.appendChild(div);
  scrollToBottom();
}

/* ─── Append typing indicator ────────────────────────────── */
function appendTyping() {
  const id = 'typing-' + Date.now();
  const div = document.createElement('div');
  div.className = 'message bot-message';
  div.id = id;
  div.innerHTML = `
    <div class="bot-icon">🌴</div>
    <div class="bubble typing">
      <span></span><span></span><span></span>
    </div>`;
  messages.appendChild(div);
  scrollToBottom();
  return id;
}

function removeTyping(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

/* ─────────────────────────────────────────────────────────
   SECTION PARSING — split the LLM answer into titled sections
   ───────────────────────────────────────────────────────── */
function parseSections(markdown) {
  const lines = (markdown || '').split('\n');
  const sections = [];
  let current = null;

  const headingRe  = /^\s*#{1,4}\s+(.+?)\s*$/;                 // ## Heading
  const numBoldRe  = /^\s*\d+[.)]\s*\*\*(.+?)\*\*\s*:?\s*$/;    // 1. **Heading**
  const boldOnlyRe = /^\s*\*\*(.+?)\*\*\s*:?\s*$/;             // **Heading**
  const numPlainRe = /^\s*\d+[.)]\s+([A-Za-z][\w &/-]{2,38})\s*:?\s*$/; // 1. Heading

  function push(title) {
    current = { title: cleanTitle(title), body: [] };
    sections.push(current);
  }

  for (const line of lines) {
    let m;
    if ((m = line.match(headingRe)))      push(m[1]);
    else if ((m = line.match(numBoldRe))) push(m[1]);
    // plain "1. Flights" only counts as a heading if it names a known section —
    // avoids splitting on numbered list items like "1. Visit the Eiffel Tower"
    else if ((m = line.match(numPlainRe)) && classify(cleanTitle(m[1])) !== 'generic') push(m[1]);
    else if ((m = line.match(boldOnlyRe)) && m[1].length <= 38) push(m[1]);
    else {
      if (!current) push('Trip Summary');
      current.body.push(line);
    }
  }

  return sections
    .map(s => ({ title: s.title, body: s.body.join('\n').trim() }))
    .filter(s => s.body.length > 0);
}

function cleanTitle(t) {
  return t.replace(/^\s*\d+[.)]\s*/, '')   // leading "1."
          .replace(/[*#:_]/g, '')          // stray markdown
          .trim();
}

/* ─── Map a section title to a card type ─────────────────── */
function classify(title) {
  const t = title.toLowerCase();
  if (/(summary|overview|at a glance|snapshot|trip detail)/.test(t)) return 'summary';
  if (/(flight|air|fly|airport|airfare)/.test(t))                    return 'flight';
  if (/(hotel|stay|accommodation|lodging|where to sleep)/.test(t))   return 'hotel';
  if (/(itinerary|day-?by-?day|schedule|daily|day plan)/.test(t))    return 'itinerary';
  if (/(budget|cost|estimate|expense|price|spend)/.test(t))          return 'budget';
  if (/(recommend|tip|advice|note|suggestion|final|good to know|know before)/.test(t)) return 'tips';
  return 'generic';
}

/* ─── Build one themed card ──────────────────────────────── */
function buildCard(type, bodyHtml, index) {
  const style = `style="animation-delay:${(index * 0.08).toFixed(2)}s"`;

  switch (type) {
    case 'flight':
      return `<div class="tcard tcard-flight" ${style}>
        <div class="tcard-head">
          <span class="th-icon">✈️</span>
          <span class="th-title">BOARDING PASS</span>
          <span class="th-air">TRIPMATE AIR</span>
        </div>
        <div class="tcard-body response-content">${bodyHtml}</div>
        <div class="tcard-stub"><div class="barcode"></div></div>
      </div>`;

    case 'hotel':
      return `<div class="tcard tcard-hotel" ${style}>
        <div class="keycard-stripe"></div>
        <div class="tcard-head">
          <span class="th-icon">🏨</span>
          <span class="th-title">YOUR STAY</span>
          <span class="chip"></span>
        </div>
        <div class="tcard-body response-content">${bodyHtml}</div>
      </div>`;

    case 'itinerary':
      return `<div class="tcard tcard-itinerary" ${style}>
        <div class="tcard-head">
          <span class="th-icon">🗺️</span>
          <span class="th-title">ITINERARY</span>
          <span class="th-air">DAY BY DAY</span>
        </div>
        <div class="tcard-body response-content">${bodyHtml}</div>
      </div>`;

    case 'budget':
      return `<div class="tcard tcard-budget" ${style}>
        <div class="receipt-head"><span class="th-icon">💰</span><span>ESTIMATED BUDGET</span></div>
        <div class="tcard-body response-content receipt-body">${bodyHtml}</div>
      </div>`;

    case 'summary':
      return `<div class="tcard tcard-summary" ${style}>
        <div class="postcard-head">
          <div class="stamp">✦</div>
          <div class="pc-title">TRIP SUMMARY</div>
          <div class="pc-sub">Your getaway at a glance</div>
        </div>
        <div class="tcard-body response-content">${bodyHtml}</div>
      </div>`;

    case 'tips':
      return `<div class="tcard tcard-tips" ${style}>
        <div class="tcard-head">
          <span class="th-icon">💡</span>
          <span class="th-title">GOOD TO KNOW</span>
        </div>
        <div class="tcard-body response-content">${bodyHtml}</div>
      </div>`;

    default:
      return `<div class="tcard tcard-generic" ${style}>
        <div class="tcard-head">
          <span class="th-icon">📋</span>
          <span class="th-title">DETAILS</span>
        </div>
        <div class="tcard-body response-content">${bodyHtml}</div>
      </div>`;
  }
}

/* ─── Append bot response as a deck of cards ─────────────── */
function appendBotMessage(data) {
  const div = document.createElement('div');
  div.className = 'message bot-message';

  const sections = parseSections(data.answer || '');
  const calls = data.llm_calls || 0;

  let cardsHtml = '';
  sections.forEach((sec, i) => {
    cardsHtml += buildCard(classify(sec.title), renderMarkdown(sec.body), i);
  });
  if (!cardsHtml) {
    cardsHtml = buildCard('generic', renderMarkdown(data.answer || 'No details returned.'), 0);
  }

  div.innerHTML = `
    <div class="bot-icon">🌴</div>
    <div class="tcards">
      ${cardsHtml}
      <div class="tcard-meta">✦ Planned by TripMate AI · ${calls} AI call${calls !== 1 ? 's' : ''}</div>
    </div>`;

  messages.appendChild(div);
  scrollToBottom();
}

/* ─── Append error bubble ────────────────────────────────── */
function appendError(text) {
  const div = document.createElement('div');
  div.className = 'message bot-message error';
  div.innerHTML = `
    <div class="bot-icon">⚠️</div>
    <div class="bubble error-bubble">
      <p>${escapeHtml(text)}</p>
    </div>`;
  messages.appendChild(div);
  scrollToBottom();
}

/* ─── Scroll chat to bottom ──────────────────────────────── */
function scrollToBottom() {
  chat.scrollTop = chat.scrollHeight;
}

/* ─── Markdown renderer ──────────────────────────────────── */
function renderMarkdown(text) {
  if (typeof marked !== 'undefined') return marked.parse(text);
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');
}

/* ─── HTML escape ────────────────────────────────────────── */
function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
