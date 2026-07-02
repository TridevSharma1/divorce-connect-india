async function hireLawyer(lawyerId, message) {
    const token = localStorage.getItem("jwt_token");
    const formData = new FormData();
    formData.append("lawyer_id", lawyerId);
    formData.append("message", message);
    
    try {
        const res = await fetch("/api/cases/hire", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`
            },
            body: formData
        });
        const data = await res.json();
        if (res.ok) {
            alert("Lawyer hired successfully! Case ID: " + data.case_id);
            window.location.reload();
        } else {
            alert(data.detail || "Failed to hire lawyer");
        }
    } catch (e) {
        console.error(e);
    }
}

async function respondToCase(caseId, action, responseMsg = "") {
    const token = localStorage.getItem("jwt_token");
    const formData = new FormData();
    formData.append("action", action); // ACCEPT or REJECT
    formData.append("response_msg", responseMsg);
    
    try {
        const res = await fetch(`/api/cases/${caseId}/respond`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`
            },
            body: formData
        });
        const data = await res.json();
        if (res.ok) {
            alert(`Case ${action.toLowerCase()}ed successfully`);
            window.location.reload();
        } else {
            alert(data.detail || "Failed to respond");
        }
    } catch (e) {
        console.error(e);
    }
}

async function uploadCaseDocument(caseId, documentType, file) {
    const token = localStorage.getItem("jwt_token");
    const formData = new FormData();
    formData.append("document_type", documentType);
    formData.append("file", file);
    
    try {
        const res = await fetch(`/api/cases/${caseId}/documents`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`
            },
            body: formData
        });
        const data = await res.json();
        if (res.ok) {
            alert("Document uploaded: " + data.url);
        } else {
            alert(data.detail || "Upload failed");
        }
    } catch (e) {
        console.error(e);
    }
}

async function verifyDocuments(caseId) {
    const token = localStorage.getItem("jwt_token");
    try {
        const res = await fetch(`/api/cases/documents/${caseId}/verify`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });
        const data = await res.json();
        if (res.ok) {
            alert(data.message);
            window.location.reload();
        } else {
            alert(data.detail || "Verification failed");
        }
    } catch (e) {
        console.error(e);
    }
}

async function updateWorkflowStage(caseId, stage) {
    const token = localStorage.getItem("jwt_token");
    const formData = new FormData();
    formData.append("stage", stage);
    
    try {
        const res = await fetch(`/api/cases/${caseId}/stage`, {
            method: "PUT",
            headers: {
                "Authorization": `Bearer ${token}`
            },
            body: formData
        });
        const data = await res.json();
        if (res.ok) {
            alert(data.message);
            window.location.reload();
        } else {
            alert(data.detail || "Update failed");
        }
    } catch (e) {
        console.error(e);
    }
}
