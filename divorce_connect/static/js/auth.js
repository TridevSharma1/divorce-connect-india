const Auth = {
    getToken() {
        return localStorage.getItem("access_token");
    },
    
    setToken(token) {
        localStorage.setItem("access_token", token);
    },
    
    logout() {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login/";
    },
    
    async getCurrentUser() {
        const token = this.getToken();
        if (!token) return null;
        
        try {
            const response = await fetch("/api/auth/me", {
                headers: {
                    "Authorization": "Bearer " + token,
                    "Accept": "application/json"
                }
            });
            
            if (response.ok) {
                return await response.json();
            } else {
                this.logout();
                return null;
            }
        } catch (error) {
            console.error("Failed to fetch user:", error);
            return null;
        }
    },

    async applyNavbarState() {
        const user = await this.getCurrentUser();
        
        const guestNav = document.getElementById("nav-guest");
        const clientNav = document.getElementById("nav-client");
        const lawyerNav = document.getElementById("nav-lawyer");
        const adminNav = document.getElementById("nav-admin");
        const clientStaticNav = document.getElementById("nav-client-static");
        const lawyerStaticNav = document.getElementById("nav-lawyer-static");
        const adminStaticNav = document.getElementById("nav-admin-static");
        const mobileMenus = document.querySelectorAll(".mobile-menu");

        const footerClient = document.getElementById("footer-col-client");
        const footerLawyer = document.getElementById("footer-col-lawyer");
        const footerAdmin = document.getElementById("footer-col-admin");

        if (guestNav) guestNav.style.display = "none";
        if (clientNav) clientNav.style.display = "none";
        if (lawyerNav) lawyerNav.style.display = "none";
        if (adminNav) adminNav.style.display = "none";
        if (clientStaticNav) clientStaticNav.style.display = "none";
        if (lawyerStaticNav) lawyerStaticNav.style.display = "none";
        if (adminStaticNav) adminStaticNav.style.display = "none";
        mobileMenus.forEach((menu) => menu.classList.remove("active"));

        if (footerClient) footerClient.style.display = "none";
        if (footerLawyer) footerLawyer.style.display = "none";
        if (footerAdmin) footerAdmin.style.display = "none";

        let activeRole = "guest";

        if (user) {
            if (user.role === "admin" || user.is_staff) {
                if (adminNav) adminNav.style.display = "flex";
                if (adminStaticNav) adminStaticNav.style.display = "flex";
                if (footerAdmin) footerAdmin.style.display = "block";
                activeRole = "admin";
            } else if (user.role === "lawyer") {
                if (lawyerNav) lawyerNav.style.display = "flex";
                if (lawyerStaticNav) lawyerStaticNav.style.display = "flex";
                if (footerLawyer) footerLawyer.style.display = "block";
                activeRole = "lawyer";
            } else {
                if (clientNav) clientNav.style.display = "flex";
                if (clientStaticNav) clientStaticNav.style.display = "flex";
                if (footerClient) footerClient.style.display = "block";
                activeRole = "client";
            }
            
            // Populate user's name in navbars
            const displayName = (user.full_name || user.first_name || user.username || (user.email ? user.email.split('@')[0] : '')).trim() || 'User';
            const nameElements = document.querySelectorAll(".auth-user-name");
            nameElements.forEach(el => {
                el.textContent = displayName;
            });

            // Populate user's avatar in navbars
            console.log("User data received:", user);
            console.log("Profile picture value:", user.profile_picture);
            const avatarElements = document.querySelectorAll(".auth-user-avatar");
            console.log("Avatar elements found:", avatarElements.length);
            
            avatarElements.forEach((el, idx) => {
                const initials = displayName.charAt(0).toUpperCase();

                if (user.profile_picture) {
                    console.log(`Setting image for avatar ${idx}:`, user.profile_picture);
                    el.innerHTML = `<img src="${user.profile_picture}" alt="${displayName}" class="w-full h-full object-cover rounded-full" />`;
                } else {
                    console.log(`Setting initials for avatar ${idx}: ${initials}`);
                    el.innerHTML = `<span class="text-xs font-semibold text-zinc-700">${initials}</span>`;
                }
            });
            
        } else {
            if(guestNav) guestNav.style.display = "flex";
            if(footerClient) footerClient.style.display = "block";
            activeRole = "guest";
        }

        document.body.dataset.mobileNavRole = activeRole;
    }
};

document.addEventListener("DOMContentLoaded", () => {
    Auth.applyNavbarState();

    document.addEventListener("click", (e) => {
        const logoutLink = e.target.closest(".logout-item");
        if (logoutLink) {
            e.preventDefault();
            Auth.logout();
        }
    });
});
