let chatSocket = null;
let currentCaseId = null;
let currentUserId = null; // Should be set after fetching auth/me

async function initializeChat(caseId, userId) {
    currentCaseId = caseId;
    currentUserId = userId;
    
    // Load history
    const token = localStorage.getItem("jwt_token");
    try {
        const res = await fetch(`/api/chat/${caseId}/history`, {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });
        if (res.ok) {
            const history = await res.json();
            renderChatHistory(history);
        }
    } catch (e) {
        console.error("Failed to load chat history", e);
    }
    
    // Connect WebSocket
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProtocol}//${window.location.host}/api/chat/ws/${caseId}`;
    
    chatSocket = new WebSocket(wsUrl);
    
    chatSocket.onopen = function(e) {
        console.log("Chat connected");
    };
    
    chatSocket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        appendMessage(data);
    };
    
    chatSocket.onclose = function(event) {
        console.log("Chat closed. Reconnecting in 3 seconds...");
        setTimeout(() => initializeChat(caseId, userId), 3000);
    };
}

function renderChatHistory(messages) {
    const container = document.getElementById("chat-messages");
    if (!container) return;
    container.innerHTML = "";
    messages.forEach(appendMessage);
}

function appendMessage(msg) {
    const container = document.getElementById("chat-messages");
    if (!container) return;
    
    const isMe = msg.sender_id === currentUserId;
    const div = document.createElement("div");
    div.className = `flex flex-col mb-4 ${isMe ? 'items-end' : 'items-start'}`;
    
    let innerHtml = `<div class="px-4 py-2 rounded-lg max-w-sm ${isMe ? 'bg-blue-600 text-white' : 'bg-white/10 text-white backdrop-blur-md'}">`;
    if (msg.message) {
        innerHtml += `<p class="text-sm">${msg.message}</p>`;
    }
    if (msg.file_url) {
        innerHtml += `<a href="${msg.file_url}" target="_blank" class="block mt-2 text-xs text-blue-300 underline">View Attachment</a>`;
    }
    innerHtml += `</div>`;
    
    div.innerHTML = innerHtml;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

async function sendChatMessage(message, fileUrl = null) {
    if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
        alert("Chat not connected");
        return;
    }
    const payload = {
        sender_id: currentUserId,
        message: message,
        file_url: fileUrl
    };
    chatSocket.send(JSON.stringify(payload));
}
