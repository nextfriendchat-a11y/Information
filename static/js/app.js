// API base URL
const API_BASE = window.location.origin;

// State management
let conversationHistory = [];

// DOM elements
const chatContainer = document.getElementById('chat-messages');
const inputField = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const inputForm = document.getElementById('input-form');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    addWelcomeMessage();
    inputForm.addEventListener('submit', handleSubmit);
    sendButton.addEventListener('click', handleSubmit);
    inputField.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    });
});

function addWelcomeMessage() {
    addMessage('ai', 'Hello! I\'m your AI-powered public information search assistant. You can search using any attribute like name, phone number, address, or institution. How can I help you?');
}

function handleSubmit(e) {
    e.preventDefault();
    const query = inputField.value.trim();
    
    if (!query) {
        return;
    }
    
    // Add user message to UI
    addMessage('user', query);
    inputField.value = '';
    setLoading(true);
    
    // Send to API
    sendQuery(query);
}

async function sendQuery(query) {
    try {
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query,
                conversation_history: conversationHistory
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Update conversation history
        conversationHistory.push(
            { role: 'user', content: query },
            { role: 'assistant', content: data.response }
        );
        
        // Display AI response
        displayAIResponse(data);
        
    } catch (error) {
        console.error('Error:', error);
        addMessage('ai', 'Sorry, I encountered an error processing your request. Please try again.');
    } finally {
        setLoading(false);
    }
}

function displayAIResponse(data) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message ai';
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = 'AI';
    
    const content = document.createElement('div');
    content.className = 'message-content';
    
    // Add response text
    const responseText = document.createElement('p');
    responseText.textContent = data.response;
    content.appendChild(responseText);
    
    // Add results if available
    if (data.results && data.results.length > 0) {
        const resultsDiv = document.createElement('div');
        resultsDiv.className = 'results';
        
        data.results.forEach((result, index) => {
            const resultItem = createResultItem(result, index);
            resultsDiv.appendChild(resultItem);
        });
        
        content.appendChild(resultsDiv);
    }
    
    // Add disambiguation options if needed
    if (data.needs_disambiguation && data.disambiguation_options) {
        const disambiguationDiv = document.createElement('div');
        disambiguationDiv.className = 'disambiguation-options';
        disambiguationDiv.innerHTML = '<p style="margin-bottom: 10px; font-weight: 600;">Multiple matches found. Please select one:</p>';
        
        data.disambiguation_options.forEach((option, index) => {
            const optionDiv = createDisambiguationOption(option, index, data.results);
            disambiguationDiv.appendChild(optionDiv);
        });
        
        content.appendChild(disambiguationDiv);
    }
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);
    chatContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    scrollToBottom();
}

function createResultItem(result, index) {
    const item = document.createElement('div');
    item.className = 'result-item';
    
    const title = document.createElement('h4');
    title.textContent = `Result ${index + 1}`;
    item.appendChild(title);
    
    // Display available fields
    const fields = ['name', 'phone', 'address', 'institution', 'organization'];
    fields.forEach(field => {
        if (result[field]) {
            const p = document.createElement('p');
            p.innerHTML = `<strong>${field.charAt(0).toUpperCase() + field.slice(1)}:</strong> ${result[field]}`;
            item.appendChild(p);
        }
    });
    
    // Add source link
    if (result.source_url) {
        const sourceLink = document.createElement('a');
        sourceLink.href = result.source_url;
        sourceLink.target = '_blank';
        sourceLink.textContent = 'View Source';
        sourceLink.className = 'source-link';
        item.appendChild(sourceLink);
    }
    
    // Add scraped date if available
    if (result.scraped_at) {
        const date = document.createElement('p');
        date.style.fontSize = '11px';
        date.style.color = '#6c757d';
        date.textContent = `Scraped: ${new Date(result.scraped_at).toLocaleString()}`;
        item.appendChild(date);
    }
    
    return item;
}

function createDisambiguationOption(option, index, results) {
    const div = document.createElement('div');
    div.className = 'disambiguation-option';
    div.onclick = () => selectDisambiguationOption(index, results);
    
    const title = document.createElement('h4');
    title.textContent = `Option ${index + 1}`;
    div.appendChild(title);
    
    if (option.distinguishing_features && option.distinguishing_features.length > 0) {
        option.distinguishing_features.forEach(feature => {
            const p = document.createElement('p');
            p.textContent = feature;
            div.appendChild(p);
        });
    }
    
    return div;
}

function selectDisambiguationOption(index, results) {
    if (results && results[index]) {
        const selectedResult = results[index];
        
        // Create a message showing the selected result
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai';
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = 'AI';
        
        const content = document.createElement('div');
        content.className = 'message-content';
        
        const responseText = document.createElement('p');
        responseText.textContent = 'Here are the details for your selection:';
        content.appendChild(responseText);
        
        const resultsDiv = document.createElement('div');
        resultsDiv.className = 'results';
        resultsDiv.appendChild(createResultItem(selectedResult, 0));
        content.appendChild(resultsDiv);
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(content);
        chatContainer.appendChild(messageDiv);
        
        scrollToBottom();
    }
}

function addMessage(type, text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = type === 'user' ? 'You' : 'AI';
    
    const content = document.createElement('div');
    content.className = 'message-content';
    const p = document.createElement('p');
    p.textContent = text;
    content.appendChild(p);
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);
    chatContainer.appendChild(messageDiv);
    
    scrollToBottom();
}

function setLoading(loading) {
    sendButton.disabled = loading;
    if (loading) {
        sendButton.innerHTML = '<span class="loading"></span>';
    } else {
        sendButton.textContent = 'Send';
    }
    inputField.disabled = loading;
}

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

