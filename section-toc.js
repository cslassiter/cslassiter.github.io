/* section-toc.js — auto-builds a left-hand "On this page" section navigator.
   Self-contained: injects its own scoped CSS (palette-adaptive via var() fallbacks),
   slugifies headings that lack ids, and shows a fixed sidebar only when the left
   gutter is wide enough; otherwise it stays hidden (content is unchanged on narrow
   screens). Include with:  <script src="section-toc.js" defer></script>

   Optional: a page may add nested sub-items by setting an extra CSS selector on the
   body, e.g.  <body data-section-toc-extra=".course-item h3">  — matched elements are
   listed (indented) in document order alongside the h2 sections. */
(function () {
  'use strict';

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  ready(function () {
    var primarySel = 'main h2, .container > h2';
    var extraSel = (document.body.getAttribute('data-section-toc-extra') || '').trim();
    var sel = extraSel ? primarySel + ', ' + extraSel : primarySel;

    // Collect headings (and any extra sub-items) in document order.
    var nodes = Array.prototype.slice.call(document.querySelectorAll(sel)).filter(function (h) {
      return (h.textContent || '').trim().length > 0;
    });

    function isPrimary(el) { return el.tagName.toLowerCase() === 'h2'; }
    var primaryCount = nodes.filter(isPrimary).length;
    if (primaryCount < 2) return; // nothing worth navigating

    // Inject scoped styles once.
    var style = document.createElement('style');
    style.textContent = [
      '#section-toc{position:fixed;width:200px;',
      'max-height:84vh;overflow-y:auto;z-index:50;',
      "font-family:'Inter','EB Garamond',system-ui,sans-serif;display:none;}",
      '#section-toc .toc-label{font-size:0.66rem;font-weight:600;letter-spacing:0.12em;',
      'text-transform:uppercase;color:var(--muted,#8a8a8a);margin-bottom:0.5rem;}',
      '#section-toc ul{list-style:none;margin:0;padding:0;}',
      '#section-toc li{margin:0;padding:0;}',
      '#section-toc li::before{content:none;}',
      '#section-toc a{display:block;font-size:0.76rem;line-height:1.35;text-decoration:none;',
      'color:var(--muted,#777);padding:0.25rem 0 0.25rem 0.6rem;',
      'border-left:2px solid var(--border,#e0ddd8);transition:color .12s,border-color .12s;}',
      '#section-toc a.toc-sub{font-size:0.72rem;padding-left:1.5rem;color:var(--muted,#999);}',
      '#section-toc a:hover{color:var(--indigo,#1a1a2e);border-left-color:var(--indigo,#1a1a2e);text-decoration:none;}',
      '#section-toc a.active{color:var(--indigo,#1a1a2e);border-left-color:var(--indigo,#1a1a2e);font-weight:600;}',
      '@media print{#section-toc{display:none !important;}}'
    ].join('');
    document.head.appendChild(style);

    function slugify(text) {
      var base = text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
      if (!base) base = 'section';
      var slug = base, n = 2;
      // Each heading's id is assigned to the DOM immediately after slugify runs,
      // so getElementById already catches collisions with prior headings and any
      // pre-existing ids on the page.
      while (document.getElementById(slug)) {
        slug = base + '-' + n++;
      }
      return slug;
    }

    var nav = document.createElement('nav');
    nav.id = 'section-toc';
    nav.setAttribute('aria-label', 'On this page');
    var label = document.createElement('div');
    label.className = 'toc-label';
    label.textContent = 'On this page';
    nav.appendChild(label);
    var ul = document.createElement('ul');

    var links = [];
    nodes.forEach(function (h) {
      if (!h.id) {
        h.id = slugify(h.textContent.trim());
      }
      h.style.scrollMarginTop = '1rem';
      var li = document.createElement('li');
      var a = document.createElement('a');
      a.href = '#' + h.id;
      a.textContent = h.textContent.trim();
      if (!isPrimary(h)) { a.className = 'toc-sub'; }
      li.appendChild(a);
      ul.appendChild(li);
      links.push({ a: a, h: h });
    });
    nav.appendChild(ul);
    document.body.appendChild(nav);

    // Position in the left gutter; show only when there is room beside the
    // centered content column.
    var TOC_WIDTH = 200, GAP = 24, EDGE = 12, BOTTOM_GAP = 14;
    var siteHeader = document.querySelector('.site-header');
    function place() {
      var container = document.querySelector('.container') || document.querySelector('main') || document.body;
      var rect = container.getBoundingClientRect();
      if (rect.left < TOC_WIDTH + GAP + EDGE) { nav.style.display = 'none'; return; }
      nav.style.display = 'block';
      nav.style.left = Math.max(EDGE, rect.left - TOC_WIDTH - GAP) + 'px';
      // Vertically centre, but never let the panel's top rise into the site-header
      // banner — keep the whole panel within the content (cream) area.
      var minTop = (siteHeader ? siteHeader.offsetHeight : 0) + 14;
      nav.style.maxHeight = 'none';
      var natural = nav.offsetHeight;
      var h = Math.min(natural, Math.max(0, window.innerHeight - minTop - BOTTOM_GAP));
      var topPx = Math.max(minTop, (window.innerHeight - h) / 2);
      if (topPx + h > window.innerHeight - BOTTOM_GAP) topPx = window.innerHeight - BOTTOM_GAP - h;
      if (topPx < minTop) topPx = minTop;
      nav.style.top = topPx + 'px';
      nav.style.maxHeight = (window.innerHeight - topPx - BOTTOM_GAP) + 'px';
    }
    place();
    window.addEventListener('resize', place);
    window.addEventListener('load', place);

    // Scrollspy: highlight the entry currently nearest the top.
    function onScroll() {
      var best = null, bestTop = -Infinity;
      var marker = 120; // px from top counts as "current"
      links.forEach(function (item) {
        var top = item.h.getBoundingClientRect().top;
        if (top <= marker && top > bestTop) { bestTop = top; best = item; }
      });
      if (!best) best = links[0];
      // A short final section can't bring its heading up to the marker line at
      // maximum scroll, so the loop above would keep the previous section
      // highlighted. Once the viewport reaches the end of a scrollable document,
      // force-select the last entry. The scrollHeight > innerHeight guard keeps
      // this from firing on a page that doesn't scroll (where the viewport is
      // technically "at the bottom" while the reader is still at the top).
      var doc = document.documentElement;
      var atBottom = doc.scrollHeight > window.innerHeight &&
        window.innerHeight + window.scrollY >= doc.scrollHeight - 2;
      if (atBottom) best = links[links.length - 1];
      links.forEach(function (item) {
        item.a.classList.toggle('active', item === best);
      });
    }
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  });
})();
