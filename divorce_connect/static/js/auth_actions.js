async function forgotPassword(email) {
    const payload = { email };
    try {
        const res = await fetch("/api/auth/forgot-password", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
            alert(data.message + " (Check console for debug OTP)");
            console.log("OTP Debug:", data.otp_debug);
            // In a real app, you would transition to an OTP entry screen here
        } else {
            alert(data.detail || "Failed to request password reset");
        }
    } catch (e) {
        console.error(e);
    }
}

async function resetPassword(email, otp, newPassword) {
    const payload = { email, otp, new_password: newPassword };
    try {
        const res = await fetch("/api/auth/reset-password", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
            alert(data.message);
            window.location.href = "/login";
        } else {
            alert(data.detail || "Failed to reset password");
        }
    } catch (e) {
        console.error(e);
    }
}

async function requestAccountDeletion(email) {
    const payload = { email };
    try {
        const res = await fetch("/api/auth/request-delete", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
            alert(data.message + " (Check console for debug token)");
            console.log("Token Debug:", data.token_debug);
            // A real app would just instruct the user to check email
        } else {
            alert(data.detail || "Failed to request deletion");
        }
    } catch (e) {
        console.error(e);
    }
}

async function submitAdminDeleteRequest(reason) {
    const token = localStorage.getItem("jwt_token");
    const payload = { reason };
    try {
        const res = await fetch("/api/auth/admin-delete-request", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
            alert(data.message);
        } else {
            alert(data.detail || "Failed to request deletion");
        }
    } catch (e) {
        console.error(e);
    }
}
