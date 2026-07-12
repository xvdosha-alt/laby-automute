package net.llm.screenshotbridge.core;

import java.util.function.Consumer;
import net.labymod.api.event.Subscribe;
import net.labymod.api.event.client.chat.ChatMessageSendEvent;
import net.llm.screenshotbridge.api.AutoLoginResult;
import net.llm.screenshotbridge.api.BridgePlayer;

public class MlChatSendListener {

    private final BridgePlayer bridgePlayer;
    private final Consumer<String> logger;

    public MlChatSendListener(BridgePlayer bridgePlayer, Consumer<String> logger) {
        this.bridgePlayer = bridgePlayer;
        this.logger = logger;
    }

    @Subscribe
    public void onChatSend(ChatMessageSendEvent event) {
        String message = event.getMessage();
        if (message == null) {
            return;
        }

        String trimmed = message.trim();
        if (!trimmed.equalsIgnoreCase("/ml") && !trimmed.equalsIgnoreCase(".ml")) {
            return;
        }

        event.setCancelled(true);
        Thread worker = new Thread(() -> {
            try {
                this.logger.accept("[ml] запуск...");
                AutoLoginResult result = this.bridgePlayer.runAutoLogin();
                AutoLoginSupport.logResult(result, this.logger);
            } catch (Exception e) {
                this.logger.accept("[ml] ошибка: " + e.getMessage());
            }
        }, "ml-chat-send");
        worker.setDaemon(true);
        worker.start();
    }
}
