(function () {
  const main = document.querySelector("[data-page-main]");
  if (main) {
    window.scrollTo({ top: 0, left: 0 });
    const heading = main.querySelector("h1");
    (heading || main).setAttribute("tabindex", "-1");
    setTimeout(function () {
      (heading || main).focus({ preventScroll: true });
    }, 0);
  }

  document.querySelectorAll("a[href]").forEach(function (link) {
    try {
      const current = new URL(window.location.href);
      const target = new URL(link.getAttribute("href"), window.location.href);
      if (current.pathname === target.pathname && current.hash === target.hash) {
        link.classList.add("active");
        link.setAttribute("aria-current", "page");
      }
    } catch (error) {
      return;
    }
  });

  const navToggle = document.querySelector("[data-nav-toggle]");
  const nav = document.querySelector("[data-nav]");
  const navClose = document.querySelector("[data-nav-close]");
  function setNav(open) {
    if (!nav || !navToggle) return;
    nav.classList.toggle("open", open);
    navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.classList.toggle("nav-open", open);
  }
  if (navToggle && nav) {
    navToggle.setAttribute("aria-expanded", "false");
    navToggle.addEventListener("click", function () {
      setNav(!nav.classList.contains("open"));
    });
    nav.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        setNav(false);
      });
    });
    if (navClose) navClose.addEventListener("click", function () { setNav(false); });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") setNav(false);
    });
  }

  const sidePanel = document.querySelector("[data-side-panel]");
  const sideToggle = document.querySelector("[data-side-toggle]");
  const sideClose = document.querySelector("[data-side-close]");
  const sideScrim = document.querySelector("[data-side-scrim]");
  function setSide(open) {
    if (!sidePanel || !sideToggle) return;
    sidePanel.classList.toggle("open", open);
    sideToggle.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.classList.toggle("side-open", open);
    if (sideScrim) sideScrim.hidden = !open;
  }
  if (sidePanel && sideToggle) {
    sideToggle.addEventListener("click", function () { setSide(!sidePanel.classList.contains("open")); });
    if (sideClose) sideClose.addEventListener("click", function () { setSide(false); });
    if (sideScrim) sideScrim.addEventListener("click", function () { setSide(false); });
    sidePanel.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () { setSide(false); });
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") setSide(false);
    });
  }

  const personalization = document.querySelector("[data-personalization-panel]");
  function setPersonalization(open) {
    if (!personalization) return;
    personalization.classList.toggle("open", open);
    personalization.setAttribute("aria-hidden", open ? "false" : "true");
    if (open) {
      const first = personalization.querySelector("select, input, button, a");
      if (first) first.focus();
    }
  }
  document.querySelectorAll("[data-open-personalization]").forEach(function (button) {
    button.addEventListener("click", function () { setPersonalization(true); });
  });
  document.querySelectorAll("[data-personalization-close]").forEach(function (button) {
    button.addEventListener("click", function () { setPersonalization(false); });
  });
  if (personalization) {
    personalization.addEventListener("click", function (event) {
      if (event.target === personalization) setPersonalization(false);
    });
  }
  const personalizationFields = document.querySelector("[data-personalization-fields]");
  const personalizationFieldsToggle = document.querySelector("[data-personalization-fields-toggle]");
  function setPersonalizationFields(open) {
    if (!personalization || !personalizationFieldsToggle) return;
    personalization.classList.toggle("fields-open", open);
    personalizationFieldsToggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (open && personalizationFields) {
      const firstField = personalizationFields.querySelector("select, input, button");
      if (firstField) firstField.focus();
    }
  }
  if (personalizationFieldsToggle) {
    personalizationFieldsToggle.addEventListener("click", function () {
      setPersonalizationFields(!personalization.classList.contains("fields-open"));
    });
  }

  document.querySelectorAll("[data-game-card]").forEach(function (card) {
    const score = card.querySelector("[data-game-score]");
    const submit = card.querySelector("[data-game-submit]");
    const feedback = card.querySelector("[data-game-feedback]");
    card.querySelectorAll("[data-game-option]").forEach(function (option) {
      option.addEventListener("click", function () {
        card.querySelectorAll("[data-game-option]").forEach(function (item) {
          item.classList.remove("selected");
        });
        option.classList.add("selected");
        if (score) score.value = option.dataset.score || score.value;
        if (feedback) feedback.textContent = option === card.querySelector("[data-game-option]") ? "Good choice. Save this practice when ready." : "Saved practice should reflect a safe next step. You can choose again.";
        if (submit) submit.disabled = false;
      });
    });
  });

  const chat = document.querySelector("[data-nour-chat]");
  if (!chat) return;
  const form = chat.querySelector("[data-chat-form]");
  const input = chat.querySelector("[data-chat-input]");
  const stream = chat.querySelector("[data-chat-stream]");
  const submit = chat.querySelector("[data-chat-submit]");
  const csrf = form ? form.querySelector('input[name="csrf_token"]') : null;
  let lastFailedMessage = "";

  function appendBubble(item) {
    if (!stream) return;
    const bubble = document.createElement("article");
    bubble.className = "chat-bubble " + (item.role === "nour" ? "nour" : "student");
    const head = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = item.role === "nour" ? "Nour" : "You";
    const risk = document.createElement("span");
    risk.className = "risk " + (item.risk_level || "steady");
    risk.textContent = item.risk_level || "steady";
    head.append(name, risk);
    const body = document.createElement("p");
    body.textContent = item.message || "";
    const time = document.createElement("small");
    time.textContent = item.created_at || "";
    if (item.retry) {
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "link-button";
      retry.textContent = "Retry";
      retry.addEventListener("click", function () {
        if (input) input.value = lastFailedMessage;
        if (form) form.requestSubmit();
      });
      bubble.append(head, body, retry, time);
      stream.appendChild(bubble);
      stream.scrollTop = stream.scrollHeight;
      return bubble;
    }
    bubble.append(head, body, time);
    stream.appendChild(bubble);
    stream.scrollTop = stream.scrollHeight;
    return bubble;
  }

  function setBusy(busy) {
    if (submit) {
      submit.disabled = busy;
      submit.dataset.originalText = submit.dataset.originalText || submit.textContent;
      submit.textContent = busy ? "Sending..." : submit.dataset.originalText;
    }
  }

  function showError(message) {
    appendBubble({ role: "nour", risk_level: "watch", message: message || "Something went wrong. Try again.", created_at: "", retry: true });
  }

  if (form && input) {
    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
      }
    });
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      const message = input.value.trim();
      if (message.length < 4) return;
      setBusy(true);
      const loading = appendBubble({ role: "nour", risk_level: "steady", message: "Nour is thinking...", created_at: "" });
      try {
        const response = await fetch(chat.dataset.endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf ? csrf.value : "",
          },
          body: JSON.stringify({ message }),
        });
        const payload = await response.json();
        if (loading) loading.remove();
        if (!response.ok || !payload.ok) {
          lastFailedMessage = message;
          showError(payload.error);
          return;
        }
        input.value = "";
        appendBubble(payload.user_message);
        appendBubble(payload.nour_message);
      } catch (error) {
        if (loading) loading.remove();
        lastFailedMessage = message;
        showError("Connection problem. Your message was not saved.");
      } finally {
        setBusy(false);
        input.focus();
      }
    });
  }

  document.querySelectorAll("[data-chat-suggestion]").forEach(function (button) {
    button.addEventListener("click", function () {
      if (!input) return;
      input.value = button.dataset.chatSuggestion || "";
      input.focus();
    });
  });
  if (stream) {
    stream.scrollTop = stream.scrollHeight;
  }
  const clearChat = document.querySelector("[data-clear-chat]");
  if (clearChat && stream) {
    clearChat.addEventListener("click", function () {
      stream.innerHTML = "";
      appendBubble({ role: "nour", risk_level: "steady", message: "Visible chat cleared. Saved history remains available after refresh.", created_at: "" });
    });
  }
})();
