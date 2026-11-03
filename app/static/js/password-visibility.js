(() => {
    "use strict";

    function initPasswordVisibility() {
        const button = document.querySelector("[data-password-toggle]");
        if (!button) return;
        const input = document.getElementById(button.getAttribute("aria-controls"));
        if (!input || input.tagName !== "INPUT") return;

        button.addEventListener("click", () => {
            const showing = input.type === "password";
            input.type = showing ? "text" : "password";
            button.setAttribute("aria-label", showing ? "Hide password" : "Show password");
            button.setAttribute("title", showing ? "Hide password" : "Show password");
            button.setAttribute("aria-pressed", String(showing));
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initPasswordVisibility, { once: true });
    } else {
        initPasswordVisibility();
    }
})();
