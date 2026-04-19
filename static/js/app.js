/* ════════════════════════════════════════════════════════════════════════
   SchoolMind AI v21 — Core JavaScript
   No external dependencies. ES2018+ compatible.
   ════════════════════════════════════════════════════════════════════════ */
(function(){
  'use strict';

  // ─── 1. Apply saved A11Y settings before paint ──────────────────────
  var fs = localStorage.getItem('sm-fs');
  if (fs && /^\d+px$/.test(fs)) {
    document.documentElement.style.setProperty('--fs-base', fs);
  }
  if (localStorage.getItem('sm-ct') === 'high') {
    document.documentElement.setAttribute('data-contrast', 'high');
  }
  if (localStorage.getItem('sm-dys') === '1') {
    document.body && document.body.classList.add('dyslexia');
  }
  if (localStorage.getItem('sm-rm') === '1') {
    document.body && document.body.classList.add('reduce-motion');
  }
})();

/* ─── 2. Sound system (subtle audio feedback) ───────────────────────────── */
var SM = window.SM || {};
SM.sound = {
  enabled: localStorage.getItem('sm-snd') !== 'off',
  ctx: null,
  init: function() {
    if (this.ctx) return this.ctx;
    try {
      var Ctx = window.AudioContext || window.webkitAudioContext;
      if (Ctx) this.ctx = new Ctx();
    } catch (e) { /* ignore */ }
    return this.ctx;
  },
  play: function(freq, dur, type, vol, delay) {
    if (!this.enabled) return;
    if (document.body.classList.contains('reduce-motion')) return;
    var ctx = this.init();
    if (!ctx) return;
    try {
      var osc = ctx.createOscillator();
      var gain = ctx.createGain();
      var t = ctx.currentTime + (delay || 0);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = type || 'sine';
      osc.frequency.setValueAtTime(freq, t);
      gain.gain.setValueAtTime(0, t);
      gain.gain.linearRampToValueAtTime(vol || 0.05, t + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.001, t + dur);
      osc.start(t);
      osc.stop(t + dur + 0.05);
    } catch (e) { /* ignore */ }
  },
  click: function() { this.play(880, 0.06, 'sine', 0.04); },
  ok:    function() { this.play(523, 0.08); this.play(659, 0.1, 'sine', 0.06, 0.08); this.play(784, 0.15, 'sine', 0.06, 0.18); },
  pop:   function() { this.play(660, 0.06, 'sine', 0.05); this.play(880, 0.08, 'sine', 0.05, 0.07); },
  warn:  function() { this.play(300, 0.15, 'sawtooth', 0.05); this.play(260, 0.2, 'sawtooth', 0.04, 0.18); },
  toggle: function() {
    this.enabled = !this.enabled;
    localStorage.setItem('sm-snd', this.enabled ? 'on' : 'off');
    if (this.enabled) this.ok();
  }
};

// Backwards-compatible global aliases (used by older inline code if any)
window.playClick = function(){ SM.sound.click(); };
window.playOk    = function(){ SM.sound.ok(); };
window.playPop   = function(){ SM.sound.pop(); };
window.playWarn  = function(){ SM.sound.warn(); };

/* ─── 3. Toast notifications ────────────────────────────────────────────── */
SM.toast = function(message, type, duration) {
  type = type || 'info';
  duration = duration || 3500;
  var wrap = document.getElementById('toast-wrap');
  if (!wrap) {
    wrap = document.createElement('div');
    wrap.id = 'toast-wrap';
    wrap.className = 'toast-wrap';
    document.body.appendChild(wrap);
  }
  var icons = { success: '✅', error: '❌', warning: '⚠️', info: '💡' };
  var t = document.createElement('div');
  t.className = 'toast ' + type;
  t.setAttribute('role', 'alert');

  var icon = document.createElement('span');
  icon.style.fontSize = '1.1rem';
  icon.textContent = icons[type] || '💬';

  var msg = document.createElement('span');
  msg.style.flex = '1';
  msg.textContent = message; // Safe: textContent prevents XSS

  var close = document.createElement('button');
  close.className = 'close';
  close.setAttribute('aria-label', 'Close');
  close.textContent = '×';
  close.onclick = function(){ t.remove(); };

  t.appendChild(icon);
  t.appendChild(msg);
  t.appendChild(close);
  wrap.appendChild(t);

  if (type === 'success') SM.sound.pop();
  else if (type === 'error') SM.sound.warn();
  else SM.sound.click();

  setTimeout(function() {
    t.style.transition = 'opacity .4s, transform .4s';
    t.style.opacity = '0';
    t.style.transform = 'translateX(20px)';
    setTimeout(function(){ if (t.parentNode) t.remove(); }, 420);
  }, duration);
};
window.toast = SM.toast;

/* ─── 4. Sidebar control ─────────────────────────────────────────────────── */
SM.sidebar = {
  toggle: function() {
    var s = document.getElementById('sidebar');
    var o = document.getElementById('sidebar-overlay');
    var b = document.getElementById('hamburger-btn');
    if (!s) return;
    var open = s.classList.toggle('open');
    if (o) o.classList.toggle('show', open);
    if (b) b.setAttribute('aria-expanded', String(open));
    SM.sound.click();
    // Trap focus when open
    if (open) {
      var firstLink = s.querySelector('.sb-link');
      if (firstLink) firstLink.focus();
    }
  },
  close: function() {
    var s = document.getElementById('sidebar');
    var o = document.getElementById('sidebar-overlay');
    var b = document.getElementById('hamburger-btn');
    if (s) s.classList.remove('open');
    if (o) o.classList.remove('show');
    if (b) b.setAttribute('aria-expanded', 'false');
  }
};
window.toggleSidebar = function(){ SM.sidebar.toggle(); };
window.closeSidebar = function(){ SM.sidebar.close(); };

/* ─── 5. A11Y controls ──────────────────────────────────────────────────── */
SM.a11y = {
  applyFontSize: function(px) {
    px = Math.max(12, Math.min(22, parseInt(px, 10) || 16));
    document.documentElement.style.setProperty('--fs-base', px + 'px');
    localStorage.setItem('sm-fs', px + 'px');
  },
  incFont: function() {
    var cur = parseInt(getComputedStyle(document.documentElement)
              .getPropertyValue('--fs-base') || '16', 10);
    this.applyFontSize(cur + 1); SM.sound.click();
  },
  decFont: function() {
    var cur = parseInt(getComputedStyle(document.documentElement)
              .getPropertyValue('--fs-base') || '16', 10);
    this.applyFontSize(cur - 1); SM.sound.click();
  },
  resetFont: function() { this.applyFontSize(16); SM.sound.click(); },
  toggleContrast: function() {
    var on = document.documentElement.getAttribute('data-contrast') !== 'high';
    document.documentElement.setAttribute('data-contrast', on ? 'high' : 'normal');
    localStorage.setItem('sm-ct', on ? 'high' : 'normal');
    SM.sound.click();
  },
  toggleDyslexia: function() {
    var on = document.body.classList.toggle('dyslexia');
    localStorage.setItem('sm-dys', on ? '1' : '0');
    SM.sound.click();
  },
  toggleReduceMotion: function() {
    var on = document.body.classList.toggle('reduce-motion');
    localStorage.setItem('sm-rm', on ? '1' : '0');
    SM.sound.click();
  }
};
// Backwards-compatible aliases
window.incFont = function(){ SM.a11y.incFont(); };
window.decFont = function(){ SM.a11y.decFont(); };
window.resetFont = function(){ SM.a11y.resetFont(); };
window.toggleContrast = function(){ SM.a11y.toggleContrast(); };
window.toggleDyslexia = function(){ SM.a11y.toggleDyslexia(); };
window.toggleReduceMotion = function(){ SM.a11y.toggleReduceMotion(); };
window.toggleSounds = function(){ SM.sound.toggle(); };

/* ─── 6. CSRF helper ────────────────────────────────────────────────────── */
SM.getCsrf = function() {
  var meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute('content') : '';
};

/* Wrapper for fetch that includes CSRF + JSON for POSTs */
SM.fetch = function(url, options) {
  options = options || {};
  options.credentials = 'same-origin';
  options.headers = options.headers || {};
  if ((options.method || 'GET').toUpperCase() !== 'GET') {
    options.headers['X-CSRF-Token'] = SM.getCsrf();
    if (!options.headers['Content-Type'] && options.body && typeof options.body === 'object') {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }
  }
  return fetch(url, options);
};

/* ─── 7. Mood selector (used on multiple pages) ─────────────────────────── */
window.selectMood = function(btn, value) {
  document.querySelectorAll('.mood-btn').forEach(function(b) {
    b.classList.remove('selected');
    b.setAttribute('aria-pressed', 'false');
  });
  btn.classList.add('selected');
  btn.setAttribute('aria-pressed', 'true');
  var input = document.getElementById('mood-input');
  if (input) input.value = value;
  SM.sound.pop();
};

/* ─── 8. Risk bar coloring + count-up + intersection animations ─────────── */
function riskColor(score) {
  if (score < 2.5) return '#22c55e';
  if (score < 5)   return '#f59e0b';
  if (score < 7.5) return '#ef4444';
  return '#9d174d';
}

document.addEventListener('DOMContentLoaded', function() {
  // Risk bars
  document.querySelectorAll('.rbar-fill[data-score]').forEach(function(b) {
    var s = parseFloat(b.dataset.score) || 0;
    setTimeout(function() {
      b.style.width = Math.min(s / 10 * 100, 100) + '%';
      b.style.background = riskColor(s);
    }, 200);
  });

  // Count-up numbers
  document.querySelectorAll('[data-count]').forEach(function(el) {
    var target = parseFloat(el.dataset.count);
    if (isNaN(target)) return;
    var dur = 1000;
    var start = performance.now();
    function step(ts) {
      var p = Math.min((ts - start) / dur, 1);
      var ease = 1 - Math.pow(1 - p, 3);
      var cur = target * ease;
      el.textContent = Number.isInteger(target)
        ? Math.round(cur).toString()
        : cur.toFixed(1);
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });

  // Auto-dismiss flash messages
  document.querySelectorAll('.flash-msg').forEach(function(el) {
    setTimeout(function() {
      el.style.transition = 'opacity .4s, max-height .4s, padding .4s, margin .4s';
      el.style.opacity = '0';
      el.style.maxHeight = '0';
      el.style.padding = '0';
      el.style.margin = '0';
      setTimeout(function(){ if (el.parentNode) el.remove(); }, 420);
    }, 5000);
  });

  // Hamburger button
  var hamburger = document.getElementById('hamburger-btn');
  if (hamburger) {
    hamburger.addEventListener('click', function(){ SM.sidebar.toggle(); });
  }
  var overlay = document.getElementById('sidebar-overlay');
  if (overlay) {
    overlay.addEventListener('click', function(){ SM.sidebar.close(); });
  }

  // Close sidebar on Escape
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') SM.sidebar.close();
  });

  // Auto-close sidebar on viewport resize
  window.addEventListener('resize', function() {
    if (window.innerWidth > 768) SM.sidebar.close();
  });

  // Page loader done
  var loader = document.getElementById('page-loader');
  if (loader) {
    setTimeout(function() {
      loader.classList.add('done');
      setTimeout(function(){ if (loader.parentNode) loader.remove(); }, 500);
    }, 100);
  }

  // Pre-select middle mood button if none selected
  var moodBtns = document.querySelectorAll('.mood-btn');
  if (moodBtns.length > 0 && !document.querySelector('.mood-btn.selected')) {
    var mid = moodBtns[Math.floor(moodBtns.length / 2)];
    if (mid) {
      mid.classList.add('selected');
      mid.setAttribute('aria-pressed', 'true');
      var input = document.getElementById('mood-input');
      if (input && !input.value) input.value = mid.dataset.mood || '3';
    }
  }
});

/* ─── 9. Online / Offline banner ────────────────────────────────────────── */
window.addEventListener('offline', function() {
  SM.toast(window.SM_I18N && SM_I18N.offline || 'Offline', 'error', 5000);
});
window.addEventListener('online', function() {
  SM.toast(window.SM_I18N && SM_I18N.online || 'Back online', 'success', 3000);
});

/* ─── 10. Keep-alive ping (helps avoid free-tier sleep) ─────────────────── */
setInterval(function() {
  fetch('/ping', { credentials: 'omit', cache: 'no-store' }).catch(function(){});
}, 600000);

/* ─── 11. Password show/hide toggle (auto-binds to .pw-toggle) ──────────── */
document.addEventListener('click', function(e) {
  var btn = e.target.closest('.pw-toggle');
  if (!btn) return;
  e.preventDefault();
  var input = btn.parentElement.querySelector('input[type="password"], input[type="text"]');
  if (!input) return;
  var isHidden = input.type === 'password';
  input.type = isHidden ? 'text' : 'password';
  btn.querySelector('i').className = isHidden ? 'bi bi-eye-slash' : 'bi bi-eye';
});

/* ─── 12. Form submission protection (prevent double-submit) ────────────── */
document.addEventListener('submit', function(e) {
  var form = e.target;
  if (!(form instanceof HTMLFormElement)) return;
  var btns = form.querySelectorAll('button[type="submit"], input[type="submit"]');
  btns.forEach(function(b) {
    if (b.disabled) return;
    setTimeout(function() {
      b.disabled = true;
      b.dataset.originalText = b.innerHTML;
      b.innerHTML = '<i class="bi bi-hourglass-split"></i> ...';
    }, 0);
    // Re-enable after 8 seconds in case of error
    setTimeout(function() {
      b.disabled = false;
      if (b.dataset.originalText) b.innerHTML = b.dataset.originalText;
    }, 8000);
  });
});

/* Expose for module-style use if needed */
window.SM = SM;

/* ─────────────────────────────────────────────────────────────────────────
   13. THEME TOGGLE — Cinematic wipe transition, saves to localStorage
   ───────────────────────────────────────────────────────────────────────── */
SM.theme = {
  current: function(){
    return document.documentElement.getAttribute('data-theme') || 'dark';
  },
  apply: function(theme, animate){
    var root = document.documentElement;
    var overlay = document.getElementById('theme-transition');

    if (animate && overlay && !document.body.classList.contains('reduce-motion')) {
      // Cinematic radial wipe
      overlay.classList.add('active');
      // Color the overlay with the NEW theme's color for a smoother crossover
      overlay.style.background = (theme === 'dark')
        ? 'radial-gradient(circle at var(--tx,50%) var(--ty,50%), #0b1020 0%, #141b34 60%, transparent 100%)'
        : 'radial-gradient(circle at var(--tx,50%) var(--ty,50%), #fef7ee 0%, #fef3e2 60%, transparent 100%)';

      setTimeout(function(){
        root.setAttribute('data-theme', theme);
      }, 200);
      setTimeout(function(){
        overlay.classList.remove('active');
      }, 800);
    } else {
      root.setAttribute('data-theme', theme);
    }

    try { localStorage.setItem('sm_theme', theme); } catch(e){}

    // Update meta theme-color
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', theme === 'dark' ? '#0b1020' : '#fef7ee');

    // Sync with server for session fallback
    fetch('/set-theme/' + theme, { credentials: 'same-origin' }).catch(function(){});
  },
  toggle: function(event){
    var next = this.current() === 'dark' ? 'light' : 'dark';
    // Compute cursor position for radial animation origin
    if (event) {
      var x = (event.clientX / window.innerWidth * 100).toFixed(0);
      var y = (event.clientY / window.innerHeight * 100).toFixed(0);
      document.documentElement.style.setProperty('--tx', x + '%');
      document.documentElement.style.setProperty('--ty', y + '%');
    }
    this.apply(next, true);
    SM.sound.pop();
  }
};

document.addEventListener('DOMContentLoaded', function(){
  var btn = document.getElementById('theme-toggle');
  if (btn) {
    btn.addEventListener('click', function(e){ SM.theme.toggle(e); });
  }
});

/* ─────────────────────────────────────────────────────────────────────────
   14. DESKTOP SIDEBAR TOGGLE — Hide/show with animation
   ───────────────────────────────────────────────────────────────────────── */
SM.sidebarDesktop = {
  toggle: function(){
    var hidden = document.body.classList.toggle('sidebar-hidden');
    try { localStorage.setItem('sm_sidebar_hidden', hidden ? '1' : '0'); } catch(e){}
    SM.sound.click();
    // Accessibility announcement
    var msg = hidden
      ? (window.SM_I18N && SM_I18N.sidebar_hidden || 'Sidebar hidden')
      : (window.SM_I18N && SM_I18N.sidebar_shown || 'Sidebar shown');
    SM.toast(msg, 'info', 1500);
  }
};

document.addEventListener('DOMContentLoaded', function(){
  var btn = document.getElementById('sidebar-toggle-btn');
  if (btn) {
    btn.addEventListener('click', function(){
      // On mobile, use the mobile drawer logic instead
      if (window.innerWidth <= 768) {
        SM.sidebar.toggle();
      } else {
        SM.sidebarDesktop.toggle();
      }
    });
  }
});

/* ─────────────────────────────────────────────────────────────────────────
   15. GEOLOCATION PROMPT — Asked once per user after login
   ───────────────────────────────────────────────────────────────────────── */
SM.geo = {
  shouldAsk: function(){
    // Skip if user already decided (accepted, declined, or skipped)
    try {
      var decision = localStorage.getItem('sm_geo_decision');
      if (decision) return false;
    } catch(e){}
    // Only if geolocation API exists
    return ('geolocation' in navigator);
  },
  showBanner: function(){
    var banner = document.getElementById('geo-banner');
    if (!banner) return;
    // Small delay so it doesn't flash on page load
    setTimeout(function(){ banner.classList.add('show'); }, 1500);
  },
  hideBanner: function(){
    var banner = document.getElementById('geo-banner');
    if (banner) banner.classList.remove('show');
  },
  allow: function(){
    var self = this;
    this.hideBanner();
    if (!navigator.geolocation) {
      try { localStorage.setItem('sm_geo_decision', 'unsupported'); } catch(e){}
      return;
    }
    navigator.geolocation.getCurrentPosition(
      function(pos){
        // Success — send to server
        SM.fetch('/api/location', {
          method: 'POST',
          body: {
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
            accuracy: Math.round(pos.coords.accuracy || 0)
          }
        }).then(function(r){ return r.json(); })
          .then(function(d){
            if (d && d.ok) {
              SM.toast(window.SM_I18N && SM_I18N.geo_thanks || 'Location saved', 'success', 3000);
            }
          }).catch(function(){});
        try { localStorage.setItem('sm_geo_decision', 'allowed'); } catch(e){}
      },
      function(err){
        // User denied or timeout
        try { localStorage.setItem('sm_geo_decision', 'denied'); } catch(e){}
        SM.toast(window.SM_I18N && SM_I18N.geo_fail || 'No location', 'info', 3000);
      },
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 300000 }
    );
  },
  decline: function(){
    this.hideBanner();
    try { localStorage.setItem('sm_geo_decision', 'skipped'); } catch(e){}
  }
};

document.addEventListener('DOMContentLoaded', function(){
  var allowBtn = document.getElementById('geo-allow');
  var declineBtn = document.getElementById('geo-decline');
  if (allowBtn) allowBtn.addEventListener('click', function(){ SM.geo.allow(); });
  if (declineBtn) declineBtn.addEventListener('click', function(){ SM.geo.decline(); });
  if (SM.geo.shouldAsk()) SM.geo.showBanner();
});

/* ─────────────────────────────────────────────────────────────────────────
   16. ASYNC NOUR CHAT — Send without page refresh
   Auto-activates on #nour-chat-form. The template provides the structure.
   ───────────────────────────────────────────────────────────────────────── */
SM.nour = {
  init: function(){
    var form = document.getElementById('nour-chat-form');
    if (!form) return;

    var input = form.querySelector('[name="message"]');
    var history = document.getElementById('nour-history') || document.getElementById('chat-history');
    var sendBtn = form.querySelector('button[type="submit"]');

    if (!input || !history) return;

    form.addEventListener('submit', function(e){
      e.preventDefault();
      var msg = (input.value || '').trim();
      if (!msg) return;
      if (sendBtn && sendBtn.disabled) return;

      // Disable send button + add user message immediately
      if (sendBtn) sendBtn.disabled = true;
      input.value = '';
      input.style.height = 'auto';

      SM.nour.appendMessage(history, 'user', msg);

      // Typing indicator
      var typing = SM.nour.appendTyping(history);

      SM.fetch('/api/companion', {
        method: 'POST',
        body: { message: msg }
      }).then(function(r){
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }).then(function(data){
        if (typing && typing.parentNode) typing.remove();
        var reply = (data && data.response) ? data.response : '...';
        SM.nour.appendMessage(history, 'ai', reply);
        if (sendBtn) sendBtn.disabled = false;
        input.focus();

        // EMERGENCY ESCALATION: if server flagged this as crisis,
        // show urgent support UI with emergency contacts.
        if (data && data.emergency) {
          SM.nour.showEmergency();
        }
      }).catch(function(err){
        if (typing && typing.parentNode) typing.remove();
        SM.toast('Connection error. Please try again.', 'error', 3500);
        if (sendBtn) sendBtn.disabled = false;
      });
    });

    // Enter to send (Shift+Enter = newline)
    input.addEventListener('keydown', function(e){
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        form.dispatchEvent(new Event('submit', { cancelable: true }));
      }
    });

    // Auto-grow textarea
    input.addEventListener('input', function(){
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 160) + 'px';
    });

    // Scroll to bottom on load
    history.scrollTop = history.scrollHeight;
  },

  appendMessage: function(historyEl, role, text){
    // Remove empty-state placeholder if present
    var empty = historyEl.querySelector('.chat-empty');
    if (empty) empty.remove();

    var wrap = document.createElement('div');
    wrap.className = 'msg msg-' + (role === 'user' ? 'user' : 'ai');

    var avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = role === 'user' ? 'U' : '🌟';

    var bubble = document.createElement('div');
    bubble.className = 'msg-bubble';
    // SECURITY: use textContent to prevent any XSS
    bubble.textContent = text;

    wrap.appendChild(avatar);
    wrap.appendChild(bubble);
    historyEl.appendChild(wrap);

    // Smooth scroll
    setTimeout(function(){
      historyEl.scrollTop = historyEl.scrollHeight;
    }, 20);
  },

  appendTyping: function(historyEl){
    var wrap = document.createElement('div');
    wrap.className = 'msg msg-ai msg-typing';
    wrap.innerHTML =
      '<div class="msg-avatar" aria-hidden="true">🌟</div>' +
      '<div class="msg-bubble typing-dots">' +
        '<span></span><span></span><span></span>' +
      '</div>';
    historyEl.appendChild(wrap);
    setTimeout(function(){
      historyEl.scrollTop = historyEl.scrollHeight;
    }, 20);
    return wrap;
  },

  // EMERGENCY ESCALATION UI — urgent supportive modal with action buttons
  showEmergency: function(){
    // Avoid stacking multiple modals
    if (document.getElementById('nour-emergency-modal')) return;

    var lang = document.documentElement.lang || 'ar';
    var ar = lang === 'ar';

    var overlay = document.createElement('div');
    overlay.id = 'nour-emergency-modal';
    overlay.className = 'modal-backdrop';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-labelledby', 'em-modal-title');

    var title = ar ? 'أنا قلقان عليك 💙' : "I'm worried about you 💙";
    var body1 = ar
      ? 'إذا كنت تمر بلحظة صعبة جداً، تحدثك معي مهم لكن لست وحدك — هناك أشخاص مدربون يقدرون يساعدوك الآن.'
      : "If you're in a very hard moment, talking to me matters — but you're not alone. Trained people can help you right now.";
    var body2 = ar
      ? 'أرجوك تواصل مع أحد هؤلاء:'
      : 'Please reach out to one of these:';
    var btnEmergency = ar ? '📞 اتصل بالطوارئ' : '📞 Call emergency';
    var btnEmergencyPage = ar ? '🆘 صفحة الطوارئ' : '🆘 Emergency page';
    var btnDismiss = ar ? 'أنا بخير الآن' : "I'm okay now";

    overlay.innerHTML =
      '<div class="modal" style="max-width:480px;border-top:4px solid var(--danger)">' +
        '<div class="modal-header" style="background:linear-gradient(135deg,rgba(248,113,113,.08),rgba(236,72,153,.04));border-bottom-color:rgba(248,113,113,.2)">' +
          '<h3 id="em-modal-title" style="display:flex;align-items:center;gap:.5rem;color:var(--danger-h)">' +
            '<i class="bi bi-heart-pulse-fill" style="animation:heartbeat 1.5s ease-in-out infinite"></i>' +
            title +
          '</h3>' +
        '</div>' +
        '<div class="modal-body">' +
          '<p style="margin-bottom:.75rem;line-height:1.75">' + body1 + '</p>' +
          '<p style="font-weight:700;margin-bottom:.75rem">' + body2 + '</p>' +
          '<div style="display:flex;flex-direction:column;gap:.5rem">' +
            '<a href="tel:911" class="btn btn-danger btn-lg">' + btnEmergency + '</a>' +
            '<a href="/emergency" class="btn btn-warm">' + btnEmergencyPage + '</a>' +
          '</div>' +
        '</div>' +
        '<div class="modal-footer">' +
          '<button type="button" class="btn btn-ghost" id="em-modal-dismiss">' + btnDismiss + '</button>' +
        '</div>' +
      '</div>';

    document.body.appendChild(overlay);
    var dismissBtn = document.getElementById('em-modal-dismiss');
    function close(){ overlay.remove(); }
    if (dismissBtn) dismissBtn.addEventListener('click', close);
    overlay.addEventListener('click', function(e){
      if (e.target === overlay) close();
    });
    document.addEventListener('keydown', function esc(e){
      if (e.key === 'Escape') { close(); document.removeEventListener('keydown', esc); }
    });
    // Focus dismiss for keyboard users
    setTimeout(function(){ if (dismissBtn) dismissBtn.focus(); }, 50);
  }
};

document.addEventListener('DOMContentLoaded', function(){
  SM.nour.init();
});

/* ─────────────────────────────────────────────────────────────────────────
   17. SCROLL REVEAL — Fade-up elements as they enter viewport
   ───────────────────────────────────────────────────────────────────────── */
(function(){
  if (!('IntersectionObserver' in window)) return;
  if (document.body && document.body.classList.contains('reduce-motion')) return;

  var io = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if (e.isIntersecting) {
        e.target.classList.add('sv-in');
        io.unobserve(e.target);
      }
    });
  }, { rootMargin: '0px 0px -60px 0px', threshold: 0.05 });

  document.addEventListener('DOMContentLoaded', function(){
    document.querySelectorAll('.card, .sm-card, .stat-card, .hero')
      .forEach(function(el){ io.observe(el); });
  });
})();

/* ─────────────────────────────────────────────────────────────────────────
   18. RIPPLE EFFECT on buttons
   ───────────────────────────────────────────────────────────────────────── */
document.addEventListener('click', function(e){
  var btn = e.target.closest('.btn, .btn-pri, .btn-acc, .btn-success, .btn-danger, .btn-warm');
  if (!btn) return;
  if (document.body.classList.contains('reduce-motion')) return;
  var rect = btn.getBoundingClientRect();
  var ripple = document.createElement('span');
  ripple.className = 'ripple';
  var size = Math.max(rect.width, rect.height);
  ripple.style.width = ripple.style.height = size + 'px';
  ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
  ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';
  btn.appendChild(ripple);
  setTimeout(function(){ if (ripple.parentNode) ripple.remove(); }, 650);
}, { passive: true });

/* ─────────────────────────────────────────────────────────────────────────
   19. PWA — service worker + install prompt
   ───────────────────────────────────────────────────────────────────────── */
(function(){
  if (!('serviceWorker' in navigator)) return;

  // Register SW after page load (non-blocking)
  window.addEventListener('load', function(){
    navigator.serviceWorker.register('/static/sw.js', { scope: '/' })
      .catch(function(err){ console.warn('SW register failed:', err); });
  });

  // Capture install prompt
  var deferredPrompt = null;
  window.addEventListener('beforeinstallprompt', function(e){
    e.preventDefault();
    deferredPrompt = e;
    // Reveal a subtle install hint button if one exists in the DOM
    var btn = document.getElementById('pwa-install-btn');
    if (btn) btn.style.display = 'inline-flex';
  });

  SM.pwa = {
    canInstall: function(){ return deferredPrompt !== null; },
    install: function(){
      if (!deferredPrompt) {
        // iOS fallback instructions
        var lang = document.documentElement.lang || 'ar';
        SM.toast(
          lang === 'ar'
            ? 'على iOS: اضغط زر المشاركة ثم "أضف إلى الشاشة الرئيسية"'
            : 'On iOS: tap Share then "Add to Home Screen"',
          'info', 6000
        );
        return;
      }
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then(function(choice){
        deferredPrompt = null;
        var btn = document.getElementById('pwa-install-btn');
        if (btn) btn.style.display = 'none';
        if (choice.outcome === 'accepted') {
          SM.toast('✨ ' + (document.documentElement.lang === 'ar' ? 'تم التثبيت!' : 'Installed!'), 'success');
        }
      });
    }
  };

  document.addEventListener('DOMContentLoaded', function(){
    var btn = document.getElementById('pwa-install-btn');
    if (btn) btn.addEventListener('click', function(){ SM.pwa.install(); });
  });
})();
