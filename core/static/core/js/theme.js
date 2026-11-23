
document.addEventListener("DOMContentLoaded", function () {

    const toggle = document.querySelector("[data-theme-toggle]");

    if (!toggle) return;

    const savedTheme = localStorage.getItem("safespace-theme") || "light";

    function applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);

        toggle.textContent = theme === "dark"
            ? "Light mode"
            : "Dark mode";

        toggle.setAttribute(
            "aria-label",
            theme === "dark"
                ? "Switch to light theme"
                : "Switch to dark theme"
        );

        toggle.setAttribute(
            "aria-pressed",
            theme === "dark" ? "true" : "false"
        );
    }

    applyTheme(savedTheme);

    toggle.addEventListener("click", function () {

        const currentTheme =
            document.documentElement.getAttribute("data-theme");

        const newTheme =
            currentTheme === "dark" ? "light" : "dark";

        localStorage.setItem("safespace-theme", newTheme);

        applyTheme(newTheme);
    });

});
