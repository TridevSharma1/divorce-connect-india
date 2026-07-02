async function reportUser(reportedUserId, reason, proofFileUrl = null) {
    const token = localStorage.getItem("jwt_token");
    const payload = {
        reported_user_id: reportedUserId,
        reason: reason,
        proof_file_url: proofFileUrl
    };
    
    try {
        const res = await fetch("/api/support/report-user", {
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
            alert(data.detail || "Failed to submit report");
        }
    } catch (e) {
        console.error(e);
    }
}

async function reportBug(issueText) {
    const token = localStorage.getItem("jwt_token");
    const payload = { issue_text: issueText };
    
    try {
        const res = await fetch("/api/support/report-bug", {
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
            alert(data.detail || "Failed to submit bug report");
        }
    } catch (e) {
        console.error(e);
    }
}

async function submitContactForm(name, email, message) {
    const payload = { name, email, message };
    
    try {
        const res = await fetch("/api/support/contact", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
            alert(data.message);
        } else {
            alert(data.detail || "Failed to submit contact request");
        }
    } catch (e) {
        console.error(e);
    }
}
