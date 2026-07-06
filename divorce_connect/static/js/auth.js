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

        if(guestNav) guestNav.style.display = "none";
        if(clientNav) clientNav.style.display = "none";
        if(lawyerNav) lawyerNav.style.display = "none";
        if(adminNav) adminNav.style.display = "none";

        if (user) {
            if (user.role === "admin" || user.is_staff) {
                if(adminNav) adminNav.style.display = "flex";
            } else if (user.role === "lawyer") {
                if(lawyerNav) lawyerNav.style.display = "flex";
            } else {
                if(clientNav) clientNav.style.display = "flex";
            }
            
            // Populate user's name in navbars
            const nameElements = document.querySelectorAll(".auth-user-name");
            nameElements.forEach(el => {
                el.textContent = user.first_name || user.email.split('@')[0];
            });
            
        } else {
            if(guestNav) guestNav.style.display = "flex";
        }
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
