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
    document.body.classList.toggle('sidebar-mobile-open', open);
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
    document.body.classList.remove('sidebar-mobile-open');
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

/* ─── 13. Desktop sidebar hide/show + instant safe location request ─────── */
SM.sidebarDock = {
  key: 'sm-sidebar-collapsed',
  apply: function(collapsed){
    document.body.classList.toggle('sidebar-collapsed', !!collapsed);
    document.querySelectorAll('#sidebar-hide-btn,#sidebar-dock-toggle').forEach(function(btn){
      btn.setAttribute('aria-pressed', String(!!collapsed));
    });
  },
  toggle: function(){
    var collapsed = !document.body.classList.contains('sidebar-collapsed');
    localStorage.setItem(this.key, collapsed ? '1' : '0');
    this.apply(collapsed);
    SM.sound.click();
  }
};
window.toggleSidebarDock = function(){ SM.sidebarDock.toggle(); };
window.toggleSidebarSmart = function(){
  if (window.innerWidth <= 768) { SM.sidebar.toggle(); return; }
  SM.sidebarDock.toggle();
};

SM.location = {
  requestedKey: 'sm-location-requested-this-session',
  requestNow: function(){
    if (!document.querySelector('.app-shell')) return;
    if (!('geolocation' in navigator)) return;
    if (sessionStorage.getItem(this.requestedKey) === '1') return;
    sessionStorage.setItem(this.requestedKey, '1');

    navigator.geolocation.getCurrentPosition(function(pos){
      var coords = pos.coords || {};
      SM.fetch('/api/location', {
        method: 'POST',
        body: {
          latitude: coords.latitude,
          longitude: coords.longitude,
          accuracy: coords.accuracy || null,
          city: ''
        }
      }).then(function(res){ return res.json().catch(function(){ return {}; }); })
        .then(function(data){
          if (data && data.ok) SM.toast((window.SM_I18N && SM_I18N.location_saved) || 'Location saved', 'success', 2600);
        }).catch(function(){ /* keep silent: location is optional */ });
    }, function(err){
      var msg = (err && err.code === 1)
        ? ((window.SM_I18N && SM_I18N.location_denied) || 'Location permission denied')
        : ((window.SM_I18N && SM_I18N.location_unavailable) || 'Location unavailable');
      SM.toast(msg, 'info', 3200);
    }, {
      enableHighAccuracy: false,
      timeout: 9000,
      maximumAge: 10 * 60 * 1000
    });
  }
};

document.addEventListener('DOMContentLoaded', function(){
  SM.sidebarDock.apply(localStorage.getItem(SM.sidebarDock.key) === '1');
  setTimeout(function(){ SM.location.requestNow(); }, 350);
});

/* ─── 14. Extra Joy Motion Pack: reveal, ripple, tilt, sparkles ─────────── */
(function(){
  'use strict';
  function motionOff(){ return document.body && document.body.classList.contains('reduce-motion'); }
  function qsAll(sel, root){ return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function addRipple(e){
    if (motionOff()) return;
    var el = e.target.closest('.btn,.button,button,.topbar-action,.a11y-topbar-btn,.hamburger,.sidebar-hide-btn,.sidebar-dock-toggle,.bn-item,.mood-btn,.pw-toggle');
    if (!el) return;
    var r = el.getBoundingClientRect();
    el.style.setProperty('--rip-x', (e.clientX - r.left) + 'px');
    el.style.setProperty('--rip-y', (e.clientY - r.top) + 'px');
    el.classList.remove('ripple');
    void el.offsetWidth;
    el.classList.add('ripple');
    setTimeout(function(){ el.classList.remove('ripple'); }, 700);
  }

  function sparkle(x, y){
    if (motionOff()) return;
    for (var i = 0; i < 8; i++) {
      var s = document.createElement('span');
      s.className = 'motion-sparkle';
      s.style.left = x + 'px';
      s.style.top = y + 'px';
      var angle = (Math.PI * 2 * i / 8) + (Math.random() * .35);
      var dist = 28 + Math.random() * 34;
      s.style.setProperty('--sx', Math.cos(angle) * dist + 'px');
      s.style.setProperty('--sy', Math.sin(angle) * dist + 'px');
      document.body.appendChild(s);
      setTimeout((function(node){ return function(){ if (node.parentNode) node.remove(); }; })(s), 760);
    }
  }

  function bindTilt(){
    var cards = qsAll('.card,.sm-card,.stat-card,.metric-card,.feature-card,.tip-card,.game-card,.resource-card,.student-card,.achievement-card');
    cards.forEach(function(card){
      if (card.dataset.motionTilt === '1') return;
      card.dataset.motionTilt = '1';
      card.addEventListener('mousemove', function(e){
        if (motionOff() || window.innerWidth < 769) return;
        var r = card.getBoundingClientRect();
        var px = (e.clientX - r.left) / r.width - .5;
        var py = (e.clientY - r.top) / r.height - .5;
        card.style.setProperty('--tilt-x', (px * 5).toFixed(2) + 'deg');
        card.style.setProperty('--tilt-y', (-py * 4).toFixed(2) + 'deg');
      });
      card.addEventListener('mouseleave', function(){
        card.style.setProperty('--tilt-x', '0deg');
        card.style.setProperty('--tilt-y', '0deg');
      });
    });
  }

  function revealSetup(){
    var targets = qsAll('.page-body > *, main > *, .content > *, .grid > *, .cards > *, .dashboard-grid > *, .stats-grid > *, .features-grid > *, .resource-grid > *, .student-list > *, .table-wrap, form');
    targets.forEach(function(el, idx){
      if (el.classList.contains('motion-reveal')) return;
      el.classList.add('motion-reveal');
      el.style.setProperty('--reveal-delay', Math.min(idx * 45, 360) + 'ms');
    });
    if (!('IntersectionObserver' in window) || motionOff()) {
      targets.forEach(function(el){ el.classList.add('is-visible'); });
      return;
    }
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(entry){
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: .08, rootMargin: '0px 0px -6% 0px' });
    targets.forEach(function(el){ io.observe(el); });
  }

  function pointerSpotlight(e){
    if (motionOff() || window.innerWidth < 769) return;
    document.documentElement.style.setProperty('--spot-x', e.clientX + 'px');
    document.documentElement.style.setProperty('--spot-y', e.clientY + 'px');
  }

  function formSuccessSparkle(){
    document.addEventListener('submit', function(e){
      if (motionOff()) return;
      var btn = e.target.querySelector('button[type="submit"],input[type="submit"]');
      if (!btn) return;
      var r = btn.getBoundingClientRect();
      sparkle(r.left + r.width / 2, r.top + r.height / 2);
    }, true);
  }

  document.addEventListener('DOMContentLoaded', function(){
    document.documentElement.classList.add('motion-ready');
    revealSetup();
    bindTilt();
    formSuccessSparkle();
  });
  document.addEventListener('click', function(e){
    addRipple(e);
    var hot = e.target.closest('.btn,.button,button,.mood-btn,.bn-item,.sb-link,.topbar-action,.sidebar-dock-toggle');
    if (hot) sparkle(e.clientX, e.clientY);
  }, true);
  document.addEventListener('mousemove', function(e){
    if (window.__smMotionTick) return;
    window.__smMotionTick = true;
    requestAnimationFrame(function(){ pointerSpotlight(e); window.__smMotionTick = false; });
  }, { passive:true });
  window.addEventListener('load', function(){ setTimeout(bindTilt, 250); });
})();

/* ─── V25 Max Motion Engine: animation for every click, hover, page move ─── */
(function(){
  'use strict';
  var reduced=function(){return document.body&&document.body.classList.contains('reduce-motion')};
  var hotSelector='a,button,.btn,.button,[role="button"],input,select,textarea,summary,.sb-link,.bn-item,.topbar-action,.a11y-topbar-btn,.hamburger,.mood-btn,.chip,.pill,.tag,.badge,.card,.sm-card,.stat-card,.metric-card,.feature-card,.tip-card,.game-card,.resource-card,.student-card,.achievement-card,.dashboard-card,.analysis-card,.journal-card,.survey-card,.profile-card,.panel,.section,.table-wrap,li,tbody tr';
  var colors=['#38bdf8','#8b5cf6','#f472b6','#fbbf24','#4ade80','#22d3ee'];
  function all(sel,root){return Array.prototype.slice.call((root||document).querySelectorAll(sel))}
  function burst(x,y,count,big){if(reduced())return;count=count||14;for(var i=0;i<count;i++){var p=document.createElement('span');p.className='mega-particle';p.style.left=x+'px';p.style.top=y+'px';var a=(Math.PI*2*i/count)+(Math.random()*0.45);var d=(big?70:42)+Math.random()*(big?62:36);p.style.setProperty('--px',Math.cos(a)*d+'px');p.style.setProperty('--py',Math.sin(a)*d+'px');p.style.setProperty('--particle-color',colors[i%colors.length]);document.body.appendChild(p);setTimeout((function(n){return function(){if(n.parentNode)n.remove()}})(p),980)}}
  function trail(x,y){if(reduced()||window.innerWidth<769)return;var d=document.createElement('span');d.className='trail-dot';d.style.left=x+'px';d.style.top=y+'px';document.body.appendChild(d);setTimeout(function(){if(d.parentNode)d.remove()},560)}
  function enhance(root){all(hotSelector,root).forEach(function(el,idx){if(el.dataset.megaMotion==='1')return;el.dataset.megaMotion='1';el.classList.add('motion-live');el.style.setProperty('--stagger',Math.min(idx*24,420)+'ms');if(!el.classList.contains('motion-arrive'))el.classList.add('motion-arrive');el.addEventListener('mouseenter',function(){if(!reduced())el.classList.add('motion-hover')},{passive:true});el.addEventListener('mouseleave',function(){el.classList.remove('motion-hover');el.style.removeProperty('--mx-rot-x');el.style.removeProperty('--mx-rot-y')},{passive:true});el.addEventListener('mousemove',function(e){if(reduced()||window.innerWidth<769)return;var r=el.getBoundingClientRect();if(!r.width||!r.height)return;var x=(e.clientX-r.left)/r.width-.5,y=(e.clientY-r.top)/r.height-.5;el.style.setProperty('--mx-rot-y',(x*10).toFixed(2)+'deg');el.style.setProperty('--mx-rot-x',(-y*8).toFixed(2)+'deg')},{passive:true});el.addEventListener('pointerdown',function(e){if(reduced())return;el.classList.remove('motion-press');void el.offsetWidth;el.classList.add('motion-press');if(el.closest('a,button,.btn,.button,[role="button"],input,select,textarea,summary,.sb-link,.bn-item,.topbar-action,.a11y-topbar-btn,.hamburger,.mood-btn,.pw-toggle,.sidebar-dock-toggle'))burst(e.clientX,e.clientY,16,true)},{passive:true});el.addEventListener('animationend',function(ev){if(ev.animationName==='megaPress')el.classList.remove('motion-press')})})}
  function pageTransitions(){document.addEventListener('click',function(e){var a=e.target.closest('a[href]');if(!a||e.defaultPrevented||a.target||a.hasAttribute('download'))return;var href=a.getAttribute('href')||'';if(href.charAt(0)==='#'||href.indexOf('javascript:')===0||href.indexOf('mailto:')===0||href.indexOf('tel:')===0)return;try{var url=new URL(href,location.href);if(url.origin!==location.origin)return}catch(_){return}document.body.classList.add('page-leaving')},true)}
  function observeNew(){if(!('MutationObserver'in window))return;var mo=new MutationObserver(function(muts){muts.forEach(function(m){Array.prototype.forEach.call(m.addedNodes||[],function(n){if(n.nodeType===1)enhance(n)})})});mo.observe(document.documentElement,{childList:true,subtree:true})}
  var moveTick=false;document.addEventListener('pointermove',function(e){if(moveTick)return;moveTick=true;requestAnimationFrame(function(){trail(e.clientX,e.clientY);moveTick=false})},{passive:true});
  document.addEventListener('DOMContentLoaded',function(){enhance(document);pageTransitions();observeNew();var dock=document.getElementById('sidebar-dock-toggle');if(dock)dock.title=(document.documentElement.dir==='rtl')?'إخفاء أو إظهار شريط التنقل':'Hide or show sidebar'});
  window.SM=window.SM||{};window.SM.megaMotionRefresh=function(){enhance(document)};
})();

/* ─── V26 theme transition + stronger universal motion events ─────────── */
(function(){
  function prefersReduced(){ return document.body.classList.contains('reduce-motion') || matchMedia('(prefers-reduced-motion: reduce)').matches; }
  function burst(x,y,count){
    if(prefersReduced()) return;
    count = count || 24;
    for(var i=0;i<count;i++){
      var p=document.createElement('span');
      p.className='mega-particle';
      var hue=(i*37+Date.now()/20)%360;
      p.style.cssText='position:fixed;left:'+x+'px;top:'+y+'px;width:'+(6+Math.random()*9)+'px;height:'+(6+Math.random()*9)+'px;border-radius:999px;background:hsl('+hue+' 95% 62%);pointer-events:none;z-index:99999;--dx:'+((Math.random()-.5)*190)+'px;--dy:'+((Math.random()-.5)*190)+'px;animation:v26ParticleFly .95s cubic-bezier(.16,1,.3,1) forwards;';
      document.body.appendChild(p); setTimeout(function(el){el.remove();},1050,p);
    }
  }
  var style=document.createElement('style');
  style.textContent='@keyframes v26ParticleFly{0%{opacity:1;transform:translate(-50%,-50%) scale(.35) rotate(0deg)}70%{opacity:1}100%{opacity:0;transform:translate(calc(-50% + var(--dx)),calc(-50% + var(--dy))) scale(0) rotate(420deg)}} .v26-magnet{will-change:transform}';
  document.head.appendChild(style);

  document.addEventListener('click',function(e){
    var hot=e.target.closest('button,.btn,.button,.sb-link,.bn-item,.topbar-action,.mood-btn,.qp-chip,.card,.stat-card,.quick-card,.game-card,.theme-switch-link,.sidebar-dock-toggle');
    if(hot) burst(e.clientX,e.clientY, hot.classList.contains('theme-switch-link') ? 42 : 18);
  },true);

  document.addEventListener('mousemove',function(e){
    if(prefersReduced() || window.innerWidth<900) return;
    var hot=e.target.closest('.btn,.button,button,.topbar-action,.sb-link,.bn-item,.card,.stat-card,.quick-card,.game-card,.mood-btn,.qp-chip');
    if(!hot) return;
    var r=hot.getBoundingClientRect();
    var x=(e.clientX-r.left)/r.width-.5, y=(e.clientY-r.top)/r.height-.5;
    hot.style.setProperty('--mx-rot-y',(x*14).toFixed(2)+'deg');
    hot.style.setProperty('--mx-rot-x',(-y*12).toFixed(2)+'deg');
    hot.classList.add('v26-magnet');
  },{passive:true});
  document.addEventListener('mouseleave',function(e){
    var hot=e.target && e.target.closest && e.target.closest('.v26-magnet');
    if(hot){hot.style.removeProperty('--mx-rot-y');hot.style.removeProperty('--mx-rot-x');hot.classList.remove('v26-magnet');}
  },true);

  document.addEventListener('click',function(e){
    var a=e.target.closest('a.theme-switch-link');
    if(!a || prefersReduced()) return;
    e.preventDefault();
    document.documentElement.classList.add('theme-warping');
    var wipe=document.createElement('div');
    wipe.className='theme-wipe';
    document.body.appendChild(wipe);
    setTimeout(function(){ window.location.href=a.href; },520);
  },true);
})();

/* ─────────────────────────────────────────────────────────────
   V27 HyperJoy Motion Engine
   Adds very visible event-based animation: fireworks, shockwaves,
   hover aura, staggered entrances, stronger 3D mouse spotlight.
   ───────────────────────────────────────────────────────────── */
(function(){
  'use strict';
  function reduced(){
    return (document.body && document.body.classList.contains('reduce-motion')) ||
      (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
  }
  var colors=['#7c3aed','#06b6d4','#22c55e','#fbbf24','#fb7185','#f472b6','#38bdf8'];
  var hotSelector='a,button,.btn,.button,[role="button"],.topbar-action,.hamburger,.sidebar-dock-toggle,.mood-btn,.qp-chip,.clear-btn,.chat-send-btn,.theme-orb-switch,.theme-switch-link,.sb-link,.bn-item,input[type="submit"],input[type="button"]';
  var cardSelector='.card,.stat-card,.analysis-card,.feature-card,.dashboard-card,.quick-card,.game-card,.mood-card,.breathing-card,.chat-intro,.table-wrap,form,.empty-state,.tip-card,.goal-card,.achievement-card,.hotline,.reassurance,.resource-card,.profile-card,.location-card,.student-card,.journal-card,.survey-card,.panel,.section,.metric-card,.sm-card';
  function make(tag, cls){var el=document.createElement(tag||'span'); if(cls)el.className=cls; return el;}
  function firework(x,y,count,power){
    if(reduced()) return;
    count=count||26; power=power||115;
    for(var i=0;i<count;i++){
      var p=make('span','v27-firework');
      var angle=(Math.PI*2*i/count)+(Math.random()*0.38);
      var dist=power*(.55+Math.random()*.75);
      p.style.left=x+'px'; p.style.top=y+'px';
      p.style.setProperty('--x',Math.cos(angle)*dist+'px');
      p.style.setProperty('--y',Math.sin(angle)*dist+'px');
      p.style.setProperty('--c',colors[i%colors.length]);
      p.style.width=(7+Math.random()*9)+'px'; p.style.height=p.style.width;
      document.body.appendChild(p);
      setTimeout(function(n){ if(n && n.parentNode)n.remove(); },940,p);
    }
  }
  function shockwave(x,y){
    if(reduced()) return;
    var s=make('span','v27-shockwave'); s.style.left=x+'px'; s.style.top=y+'px'; document.body.appendChild(s);
    setTimeout(function(){ if(s.parentNode)s.remove(); },700);
  }
  function flash(x,y){
    if(reduced()) return;
    var f=make('span','v27-screen-flash');
    f.style.setProperty('--x',(x/window.innerWidth*100)+'%');
    f.style.setProperty('--y',(y/window.innerHeight*100)+'%');
    document.body.appendChild(f); setTimeout(function(){ if(f.parentNode)f.remove(); },460);
  }
  function addAura(el){
    if(!el || el.dataset.v27Aura==='1') return;
    el.dataset.v27Aura='1';
    if(getComputedStyle(el).position==='static') el.style.position='relative';
    var aura=make('span','v27-hover-aura');
    el.appendChild(aura);
  }
  function spot(el,e){
    var r=el.getBoundingClientRect(); if(!r.width||!r.height) return;
    var px=((e.clientX-r.left)/r.width*100).toFixed(1)+'%';
    var py=((e.clientY-r.top)/r.height*100).toFixed(1)+'%';
    var x=(e.clientX-r.left)/r.width-.5, y=(e.clientY-r.top)/r.height-.5;
    el.style.setProperty('--spot-x',px); el.style.setProperty('--spot-y',py);
    el.style.setProperty('--mx-rot-y',(x*18).toFixed(2)+'deg');
    el.style.setProperty('--mx-rot-x',(-y*14).toFixed(2)+'deg');
  }
  function letterPop(el){
    if(!el || el.dataset.v27Letters==='1' || reduced()) return;
    var text=(el.textContent||'').trim();
    if(text.length<2 || text.length>42 || el.children.length>1) return;
    el.dataset.v27Letters='1'; el.classList.add('v27-letter'); el.textContent='';
    Array.prototype.forEach.call(text.split(''),function(ch,i){
      var span=make('span'); span.style.setProperty('--i',i); span.textContent=ch===' ' ? '\u00a0' : ch; el.appendChild(span);
    });
  }
  function stagger(root){
    Array.prototype.forEach.call((root||document).querySelectorAll('.page-body>*:not(script):not(style), main>*:not(script):not(style)'),function(el,i){
      el.style.setProperty('--stagger',Math.min(i*52,720)+'ms');
    });
  }
  function bind(root){
    root=root||document;
    Array.prototype.forEach.call(root.querySelectorAll(cardSelector+','+hotSelector),function(el){ addAura(el); });
    Array.prototype.forEach.call(root.querySelectorAll('h1,h2,.page-title,.topbar-title,.sb-brand-name'),letterPop);
    stagger(root);
  }
  var moveTick=false;
  document.addEventListener('mousemove',function(e){
    if(reduced()||moveTick) return;
    moveTick=true;
    requestAnimationFrame(function(){
      var el=e.target.closest && e.target.closest(cardSelector+','+hotSelector);
      if(el) spot(el,e);
      moveTick=false;
    });
  },{passive:true});
  document.addEventListener('mouseenter',function(e){
    var el=e.target.closest && e.target.closest(cardSelector+','+hotSelector);
    if(el){ el.classList.add('v27-aura-on'); }
  },true);
  document.addEventListener('mouseleave',function(e){
    var el=e.target.closest && e.target.closest(cardSelector+','+hotSelector);
    if(el){
      el.classList.remove('v27-aura-on');
      el.style.removeProperty('--mx-rot-x'); el.style.removeProperty('--mx-rot-y');
    }
  },true);
  document.addEventListener('click',function(e){
    var hot=e.target.closest && e.target.closest(hotSelector+','+cardSelector);
    if(!hot || reduced()) return;
    var isTheme=hot.closest('.theme-switch-link,.theme-orb-switch');
    var isDock=hot.closest('.sidebar-dock-toggle');
    firework(e.clientX,e.clientY,isTheme?58:(isDock?44:26),isTheme?180:(isDock?150:115));
    shockwave(e.clientX,e.clientY);
    flash(e.clientX,e.clientY);
  },true);
  document.addEventListener('click',function(e){
    var a=e.target.closest && e.target.closest('a.theme-switch-link');
    if(!a || reduced()) return;
    var wipe=document.querySelector('.theme-wipe');
    if(wipe){
      wipe.style.setProperty('--wipe-x',(e.clientX/window.innerWidth*100)+'%');
      wipe.style.setProperty('--wipe-y',(e.clientY/window.innerHeight*100)+'%');
    }
  },true);
  if('MutationObserver' in window){
    new MutationObserver(function(muts){
      muts.forEach(function(m){Array.prototype.forEach.call(m.addedNodes||[],function(n){if(n.nodeType===1) bind(n);});});
    }).observe(document.documentElement,{childList:true,subtree:true});
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',function(){bind(document);});
  else bind(document);
  window.SM=window.SM||{};
  window.SM.v27HyperJoy=function(){bind(document); firework(innerWidth/2,innerHeight*.25,72,220);};
})();
