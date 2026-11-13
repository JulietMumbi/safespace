
document.addEventListener("DOMContentLoaded", function () {

    const toggle = document.getElementById("sidebarToggle");
    const backdrop = document.querySelector(".sidebar-backdrop");

    const isMobile = () => window.innerWidth <= 800;

    // Restore the desktop sidebar preference
    if (!isMobile() && localStorage.getItem("moderationSidebarCollapsed") === "true") {
        document.body.classList.add("sidebar-collapsed");
    }

    function updateToggleState() {
        if (!toggle) return;

        const isOpen = isMobile()
            ? document.body.classList.contains("mobile-sidebar-open")
            : !document.body.classList.contains("sidebar-collapsed");

        toggle.setAttribute("aria-expanded", String(isOpen));
    }

    function closeMobileSidebar() {
        document.body.classList.remove("mobile-sidebar-open");
        updateToggleState();
    }

    if (toggle) {
        toggle.addEventListener("click", function () {

            if (isMobile()) {
                document.body.classList.toggle("mobile-sidebar-open");
            } else {
                document.body.classList.toggle("sidebar-collapsed");

                localStorage.setItem(
                    "moderationSidebarCollapsed",
                    document.body.classList.contains("sidebar-collapsed")
                );
            }

            updateToggleState();
        });
    }

    if (backdrop) {
        backdrop.addEventListener("click", closeMobileSidebar);
    }

    // Close mobile sidebar after selecting a navigation link
    document.querySelectorAll(".moderation-sidebar a").forEach(function (link) {
        link.addEventListener("click", function () {
            if (isMobile()) {
                closeMobileSidebar();
            }
        });
    });

    // Reset mobile state when moving between screen sizes
    window.addEventListener("resize", function () {
        if (!isMobile()) {
            document.body.classList.remove("mobile-sidebar-open");
        }

        updateToggleState();
    });

    updateToggleState();
});
