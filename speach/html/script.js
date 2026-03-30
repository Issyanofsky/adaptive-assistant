
const sendBtn = document.getElementById('send-btn');
const userInput = document.getElementById('user-input');
const chatMessages = document.getElementById('chat-messages');
const micBtn = document.getElementById('mic-btn');
const ttsToggle = document.getElementById('tts-toggle');
const voiceSelect = document.getElementById('voice-select');

// Hardcoding your test user ID
const USER_ID = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11";

// --- TEXT TO SPEECH (TTS) SETUP ---
let voices = [];
function loadVoices() {
    voices = window.speechSynthesis.getVoices();
    voiceSelect.innerHTML = '';
    
    voices.forEach((voice, index) => {
        const option = document.createElement('option');
        option.value = index;
        option.textContent = `${voice.name} (${voice.lang})`;
        
        // Auto-select Hebrew voice if found
        if (voice.lang.includes('he') || voice.lang.includes('IL')) {
            option.selected = true;
        }
        voiceSelect.appendChild(option);
    });
}

// Chrome loads voices asynchronously
window.speechSynthesis.onvoiceschanged = loadVoices;
loadVoices();

function speak(text) {
    if (!ttsToggle.checked) return;
    
    const utterance = new SpeechSynthesisUtterance(text);
    const selectedVoiceIndex = voiceSelect.value;
    
    if (selectedVoiceIndex && voices[selectedVoiceIndex]) {
        utterance.voice = voices[selectedVoiceIndex];
    }
    
    // Smooth settings for a natural assistant voice
    utterance.pitch = 1.0;
    utterance.rate = 1.0; 
    
    window.speechSynthesis.speak(utterance);
}

// --- SPEECH TO TEXT (STT) SETUP ---
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

if (!SpeechRecognition) {
    alert("הדפדפן שלך אינו תומך בזיהוי קולי. מומלץ להשתמש ב-Google Chrome.");
} else {
    const recognition = new SpeechRecognition();
    recognition.lang = 'he-IL'; // Native Hebrew recognition
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    micBtn.addEventListener('click', () => {
        try {
            recognition.start();
            micBtn.classList.add('listening');
        } catch (e) {
            // Catches error if already listening
            recognition.stop();
        }
    });

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        userInput.value = transcript;
        micBtn.classList.remove('listening');
        sendMessage(); // Auto-send triggered on speech completion
    };

    recognition.onerror = (event) => {
        console.error("STT Error: ", event.error);
        micBtn.classList.remove('listening');
    };

    recognition.onend = () => {
        micBtn.classList.remove('listening');
    };
}

// --- CHAT & API LOGIC ---
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // Append user message to chat UI
    appendMessage(message, 'user');
    userInput.value = '';

    try {
        // Send request to our FastAPI backend
        const response = await fetch('http://localhost:8000/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: USER_ID, message: message })
        });

        const data = await response.json();

        // Update UI with Assistant's answer
        appendMessage(data.response, 'assistant');
        
        // Make the computer speak the response in Hebrew!
        speak(data.response);
        
        // Update Sidebar Stats
        document.getElementById('detected-mood').innerText = `תסכול: ${data.mood.frustration}`;
        document.getElementById('used-strategy').innerText = data.strategy_used;
        document.getElementById('detected-intent').innerText = data.detected_intent;

    } catch (error) {
        console.error("Error:", error);
        appendMessage("מצטערת, משהו השתבש בתקשורת עם השרת.", 'assistant');
    }
}

function appendMessage(text, sender) {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message', sender);
    msgDiv.innerText = text;
    chatMessages.appendChild(msgDiv);
    
    // Auto scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});