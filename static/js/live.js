/*
 * BidStream live updates.
 *
 * - Opens a WebSocket for the current page (auction detail or listing feed)
 * - Reconnects with exponential backoff and keeps the connection alive with pings
 * - Applies pushed bid / closed events to the DOM
 */
(function () {
  "use strict";

  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const fmtCountdown = (ms) => {
    if (ms <= 0) return "ending…";
    const s = Math.floor(ms / 1000);
    const d = Math.floor(s / 86400);
    const h = Math.floor((s % 86400) / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    if (d > 0) return `${d}d ${h}h ${m}m`;
    if (h > 0) return `${h}h ${m}m ${sec}s`;
    return `${m}m ${sec}s`;
  };

  function connect(path, onMessage) {
    const indicator = document.getElementById("live-indicator");
    let socket;
    let retries = 0;
    let pingTimer;

    const open = () => {
      socket = new WebSocket(`${scheme}://${window.location.host}${path}`);
      socket.onopen = () => {
        retries = 0;
        indicator && indicator.classList.add("is-live");
        pingTimer = setInterval(() => socket.send(JSON.stringify({ type: "ping" })), 25000);
      };
      socket.onmessage = (event) => onMessage(JSON.parse(event.data));
      socket.onclose = (event) => {
        indicator && indicator.classList.remove("is-live");
        clearInterval(pingTimer);
        if (event.code === 4404) return; // auction does not exist; don't retry
        const delay = Math.min(30000, 1000 * 2 ** retries++);
        setTimeout(open, delay);
      };
    };
    open();
  }

  // --- Auction detail page -------------------------------------------------------
  function initAuctionPage(root) {
    const auctionId = root.dataset.auctionId;
    const userId = root.dataset.userId ? Number(root.dataset.userId) : null;
    let wasLeader = false;

    const $ = (id) => document.getElementById(id);
    const countdown = () => $("countdown");

    // Countdown ticker (re-reads the element because HTMX may swap the panel).
    setInterval(() => {
      const el = countdown();
      if (el && el.dataset.endsAt) {
        el.textContent = fmtCountdown(new Date(el.dataset.endsAt) - new Date());
      }
    }, 1000);

    const leader = $("leader-status");
    wasLeader = !!(leader && leader.textContent.trim());

    connect(`/ws/auctions/${auctionId}/`, (msg) => {
      if (msg.type === "bid") {
        $("current-price").textContent = msg.current_price;
        $("bid-count").textContent = msg.bid_count;
        const cd = countdown();
        if (cd) cd.dataset.endsAt = msg.ends_at;

        const history = $("bid-history");
        const empty = $("no-bids");
        if (empty) empty.remove();
        const li = document.createElement("li");
        li.className = "flash";
        li.innerHTML = `<span></span><span>$${msg.amount}</span>`;
        li.firstChild.textContent = msg.bidder;
        history.prepend(li);
        while (history.children.length > 10) history.lastElementChild.remove();

        const input = $("bid-amount");
        if (input) {
          input.min = msg.minimum_next_bid;
          if (Number(input.value) < Number(msg.minimum_next_bid)) input.value = msg.minimum_next_bid;
          const label = document.querySelector("label[for=bid-amount]");
          if (label) label.textContent = `Your bid (min $${msg.minimum_next_bid_display})`;
        }

        const status = $("leader-status");
        if (status && userId) {
          const isLeader = msg.leader_id === userId;
          if (isLeader) status.innerHTML = "<strong>You are the highest bidder.</strong>";
          else if (wasLeader) status.innerHTML = '<strong class="message message--warning">You have been outbid!</strong>';
          wasLeader = isLeader;
        }
        if (msg.extended) {
          const panel = $("bid-panel");
          panel && panel.classList.add("flash");
        }
      } else if (msg.type === "closed") {
        window.location.reload();
      }
    });
  }

  // --- Listing pages: live price ticker -----------------------------------------
  function initFeed() {
    connect("/ws/feed/", (msg) => {
      document.querySelectorAll(`[data-price-for="${msg.auction_id}"]`).forEach((el) => {
        if (msg.type === "bid") {
          el.textContent = `$${msg.current_price}`;
          el.classList.remove("flash");
          void el.offsetWidth; // restart animation
          el.classList.add("flash");
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const auction = document.getElementById("auction");
    if (auction) initAuctionPage(auction);
    else if (document.querySelector("[data-price-for]")) initFeed();
  });
})();
