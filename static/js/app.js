function formatChatText(text) {
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\n/g, "<br>");
}

function appendChatBubble(thread, role, message) {
    const bubble = document.createElement("article");
    bubble.className = `chat-bubble ${role}`;
    bubble.innerHTML = `
        <span class="chat-role">${role === "assistant" ? "FinanceCoach AI" : "You"}</span>
        <p>${formatChatText(message)}</p>
    `;
    thread.appendChild(bubble);
    thread.scrollTop = thread.scrollHeight;
}

function initDashboardCharts() {
    const data = window.financeCoachCharts;
    if (!data || typeof Chart === "undefined") {
        return;
    }

    const categoryCanvas = document.getElementById("categoryChart");
    const dailyCanvas = document.getElementById("dailyChart");

    if (categoryCanvas) {
        new Chart(categoryCanvas, {
            type: "doughnut",
            data: {
                labels: data.categories.labels,
                datasets: [{
                    data: data.categories.values,
                    backgroundColor: ["#667eea", "#764ba2", "#5b8def", "#2bb5a8", "#ff9a62", "#f15b7a"],
                    borderWidth: 0,
                }],
            },
            options: {
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: {
                            usePointStyle: true,
                        },
                    },
                },
                cutout: "68%",
            },
        });
    }

    if (dailyCanvas) {
        new Chart(dailyCanvas, {
            type: "bar",
            data: {
                labels: data.daily.labels,
                datasets: [{
                    label: "Spend",
                    data: data.daily.values,
                    borderRadius: 6,
                    backgroundColor: "#667eea",
                    borderWidth: 0,
                }],
            },
            options: {
                scales: {
                    x: {
                        grid: { display: false },
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: "rgba(26, 26, 46, 0.06)" },
                    },
                },
                plugins: {
                    legend: { display: false },
                },
            },
        });
    }
}

function initMoodWarnings() {
    const moodSelect = document.getElementById("expenseMood");
    const warningBox = document.getElementById("moodWarningBox");
    const warningTitle = document.getElementById("moodWarningTitle");
    const warningMessage = document.getElementById("moodWarningMessage");

    if (!moodSelect || !warningBox) {
        return;
    }

    moodSelect.addEventListener("change", async () => {
        const mood = moodSelect.value;
        if (!mood) {
            warningBox.classList.add("hidden");
            return;
        }

        const response = await fetch(`/api/mood-warning?mood=${encodeURIComponent(mood)}`);
        const data = await response.json();
        if (data.warning) {
            warningTitle.textContent = `${data.warning.mood} is a known trigger`;
            warningMessage.textContent = data.warning.message;
            warningBox.classList.remove("hidden");
        } else {
            warningBox.classList.add("hidden");
        }
    });
}

function initCoachChat() {
    const form = document.getElementById("chatForm");
    const input = document.getElementById("chatInput");
    const thread = document.getElementById("chatThread");
    const quickButtons = document.querySelectorAll(".quick-question-btn");

    if (!form || !input || !thread) {
        return;
    }

    quickButtons.forEach((button) => {
        button.addEventListener("click", () => {
            input.value = button.dataset.question || "";
            input.focus();
        });
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const message = input.value.trim();
        if (!message) {
            return;
        }

        appendChatBubble(thread, "user", message);
        input.value = "";

        const loading = document.createElement("article");
        loading.className = "chat-bubble assistant";
        loading.innerHTML = `<span class="chat-role">FinanceCoach AI</span><p class="loading-dot"></p>`;
        thread.appendChild(loading);
        thread.scrollTop = thread.scrollHeight;

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ message }),
            });
            const data = await response.json();
            loading.remove();

            if (!response.ok) {
                appendChatBubble(thread, "assistant", data.error || "I hit a snag while thinking. Try again.");
                return;
            }

            appendChatBubble(thread, "assistant", data.reply);
        } catch (_error) {
            loading.remove();
            appendChatBubble(thread, "assistant", "I could not reach the coach service just now. Try again in a moment.");
        }
    });
}

function formatCurrencyInr(amount) {
    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0,
    }).format(Number(amount || 0));
}

function initSpendSwapLab() {
    const lab = document.getElementById("swapLab");
    const amountInput = document.getElementById("swapAmount");
    const yearsInput = document.getElementById("swapYears");
    const categorySelect = document.getElementById("swapCategory");
    const projectionEl = document.getElementById("swapProjection");
    const narrativeEl = document.getElementById("swapNarrative");

    if (!lab || !amountInput || !yearsInput || !categorySelect || !projectionEl || !narrativeEl) {
        return;
    }

    const renderProjection = () => {
        const amount = Math.max(0, Number(amountInput.value || 0));
        const years = Math.max(1, Number(yearsInput.value || lab.dataset.defaultYears || 5));
        const category = categorySelect.value || "this category";
        const monthlyRate = 0.07 / 12;
        const months = years * 12;
        const projected = amount * (((1 + monthlyRate) ** months - 1) / monthlyRate);
        projectionEl.textContent = `${formatCurrencyInr(amount)}/month in ${category} can become about ${formatCurrencyInr(projected)} in ${years} years.`;
        narrativeEl.textContent = `That means every month you skip that spend pattern, future-you keeps the compounding instead of the leak.`;
    };

    categorySelect.addEventListener("change", () => {
        const selected = categorySelect.options[categorySelect.selectedIndex];
        const suggestedCut = selected?.dataset.cut;
        if (suggestedCut) {
            amountInput.value = suggestedCut;
        }
        renderProjection();
    });

    amountInput.addEventListener("input", renderProjection);
    yearsInput.addEventListener("input", renderProjection);
    renderProjection();
}

document.addEventListener("DOMContentLoaded", () => {
    initDashboardCharts();
    initMoodWarnings();
    initCoachChat();
    initSpendSwapLab();
});
