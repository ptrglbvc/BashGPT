// Unified command handling system

// Handle temperature command (shared logic)
async function handleTemperatureCommand(args) {
    if (args.length < 1) {
        showNotification("Usage: /temp <value> (0-2)", 2000);
        return;
    }
    
    const tempValue = parseFloat(args[0]);
    if (isNaN(tempValue) || tempValue < 0 || tempValue > 2) {
        showNotification("Invalid temperature value. Please enter a number between 0 and 2.", 2000);
        return;
    }
    
    await changeTemperatureCommand(tempValue);
}

// Define available commands with descriptions
const COMMANDS = {
    "help": {
        description: "Show this help message",
        handler: async (args) => {
            showHelp();
        }
    },
    "model": {
        description: "Change the AI model",
        handler: async (args) => {
            if (args.length < 1) {
                showNotification("Usage: /model <model_name>", 2000);
                return;
            }
            const modelName = args[0];
            await changeModelCommand(modelName);
        }
    },
    "temp": {
        description: "Change temperature (0-2) - Usage: /temp 0.7",
        handler: async (args) => {
            await handleTemperatureCommand(args);
        }
    },
    "rg": {
        description: "Regenerate last assistant message",
        handler: async (args) => {
            // This command is only available in chat view
            if (typeof regenerateLastMessage === 'function') {
                await regenerateLastMessage();
            } else {
                showNotification("The /rg command is only available in an active chat.", 2000);
            }
        }
    }
};

// Function to handle all commands
async function handleCommand(commandInput) {
    // Remove the leading slash and split into command and arguments
    const commandParts = commandInput.substring(1).trim().split(" ");
    const command = commandParts[0].toLowerCase();
    const args = commandParts.slice(1);
    
    // Check if command exists
    if (COMMANDS[command]) {
        await COMMANDS[command].handler(args);
    } else {
        // Show error for invalid command
        showNotification(`Invalid command: ${command}. Type /help for available commands.`, 5000);
    }
}

// Function to show help message
function showHelp() {
    let helpText = "<strong>Available commands:</strong><br><br>";
    
    for (const [command, info] of Object.entries(COMMANDS)) {
        helpText += `<strong>/${command}</strong>: ${info.description}<br>`;
    }
    
    // Show notification for 10 seconds
    showNotification(helpText, 10000);
}

// Function to change model (moved from layout.html)
async function changeModelCommand(modelName) {
    try {
        const response = await fetch("/api/change_settings", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ model: modelName }),
        });

        if (!response.ok) {
            throw new Error("Failed to change model");
        }

        const result = await response.json();
        if (result.success) {
            // Try to get the full model name from the models list
            let fullModelName = modelName;
            try {
                const modelsResponse = await fetch("/api/get_models");
                if (modelsResponse.ok) {
                    const models = await modelsResponse.json();
                    const matchedModel = models.find(
                        (model) => model.name === modelName || model.shortcut === modelName
                    );
                    if (matchedModel) {
                        fullModelName = matchedModel.name;
                    }
                }
            } catch (e) {
                console.log("Could not fetch model list for UI update");
            }

            // Update UI to reflect the change with full model name
            const modelBadge = document.getElementById("model-badge");
            if (modelBadge) {
                modelBadge.textContent = fullModelName;
            }

            // Update sidebar model display if it exists
            const sidebarCurrentModel = document.getElementById("sidebar-current-model");
            if (sidebarCurrentModel) {
                sidebarCurrentModel.textContent = fullModelName;
            }

            // Show notification with full model name
            let notificationText = `Model changed to: <span style="color: var(--primary-color);">${modelName}</span>`;

            // If we have access to the full model list, try to find the full name
            try {
                const modelsResponse = await fetch("/api/get_models");
                if (modelsResponse.ok) {
                    const models = await modelsResponse.json();
                    const matchedModel = models.find(
                        (model) => model.name === modelName || model.shortcut === modelName
                    );

                    if (matchedModel) {
                        notificationText = `Model changed to: <span style="color: var(--primary-color);">${matchedModel.name}</span>`;
                    }
                }
            } catch (e) {
                // If we can't fetch models, use the provided name
                console.log("Could not fetch model list for notification");
            }

            showNotification(notificationText, 2000);
        } else {
            showNotification(`Error changing model: ${result.error}`, 2000);
        }
    } catch (error) {
        console.error("Error changing model:", error);
        showNotification(`Error changing model: ${error.message}`, 2000);
    }
}

// Function to change temperature (moved from layout.html)
async function changeTemperatureCommand(tempValue) {
    try {
        const response = await fetch("/api/change_settings", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ temperature: tempValue }),
        });

        if (!response.ok) {
            throw new Error("Failed to change temperature");
        }

        const result = await response.json();
        if (result.success) {
            showNotification(
                `Temperature set to: <span style="color: var(--primary-color);">${tempValue}</span>`,
                2000
            );
        } else {
            showNotification(`Error changing temperature: ${result.error}`, 2000);
        }
    } catch (error) {
        console.error("Error changing temperature:", error);
        showNotification(`Error changing temperature: ${error.message}`, 2000);
    }
}

// Function to regenerate last message (moved from chat.html)
async function regenerateLastMessage() {
    // Check if we're on the home page (no messages to regenerate)
    if (window.location.pathname === "/") {
        showNotification("Cannot regenerate message in new chat screen.", 2000);
        return;
    }

    // Find the last assistant message
    const messageWrappers = document.querySelectorAll(".message-wrapper");

    // Check if there are any messages
    if (messageWrappers.length === 0) {
        showNotification("No messages found to regenerate", 2000);
        return;
    }

    // Check if the last message is a user message
    const lastMessage = messageWrappers[messageWrappers.length - 1];
    if (lastMessage.classList.contains("user")) {
        showNotification("The last message was from you. Cannot regenerate user messages.", 2000);
        return;
    }

    // Find the last assistant message
    let lastAssistantIndex = -1;
    for (let i = messageWrappers.length - 1; i >= 0; i--) {
        if (messageWrappers[i].classList.contains("assistant")) {
            lastAssistantIndex = i;
            break;
        }
    }

    if (lastAssistantIndex === -1) {
        showNotification("No assistant message found to regenerate", 2000);
        return;
    }

    // Call the existing regenerate function
    const lastAssistantMessage = messageWrappers[lastAssistantIndex];
    if (typeof regenerateMessage === 'function') {
        regenerateMessage(lastAssistantMessage);
    }
}