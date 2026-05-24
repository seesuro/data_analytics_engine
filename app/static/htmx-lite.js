(() => {
  async function request(element, method, url) {
    const targetSelector = element.getAttribute("hx-target");
    const swap = element.getAttribute("hx-swap") || "innerHTML";
    const target = targetSelector ? document.querySelector(targetSelector) : element;
    const options = { method, headers: { "HX-Request": "true" } };

    if (element.tagName === "FORM") {
      options.body = new FormData(element);
    }

    const response = await fetch(url, options);
    const html = await response.text();
    swapHtml(target, html, swap);
    if (element.tagName === "FORM" && response.ok) {
      element.reset();
    }
  }

  function swapHtml(target, html, swap) {
    const template = document.createElement("template");
    template.innerHTML = html;
    template.content.querySelectorAll("[hx-swap-oob]").forEach((node) => {
      const existing = document.getElementById(node.id);
      if (existing) {
        existing.innerHTML = node.innerHTML;
      }
      node.remove();
    });

    const payload = template.innerHTML;
    if (swap === "afterbegin") {
      target.insertAdjacentHTML("afterbegin", payload);
    } else {
      target.innerHTML = payload;
    }
  }

  document.addEventListener("submit", (event) => {
    const form = event.target.closest("form[hx-post]");
    if (!form) {
      return;
    }
    event.preventDefault();
    request(form, "POST", form.getAttribute("hx-post"));
  });

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[hx-get]");
    if (!trigger) {
      return;
    }
    event.preventDefault();
    request(trigger, "GET", trigger.getAttribute("hx-get"));
  });

  window.htmx = { version: "local-lite" };
})();
