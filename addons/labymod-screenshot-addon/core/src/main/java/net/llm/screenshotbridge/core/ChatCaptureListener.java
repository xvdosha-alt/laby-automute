package net.llm.screenshotbridge.core;

import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import net.labymod.api.client.chat.ChatMessage;
import net.labymod.api.event.Subscribe;
import net.labymod.api.event.client.chat.ChatMessageAddEvent;
import net.labymod.api.event.client.chat.ChatReceiveEvent;
import net.labymod.api.mojang.GameProfile;
import net.llm.screenshotbridge.api.BridgePlayer;

public class ChatCaptureListener {

    private static final DateTimeFormatter TIME_FORMAT = DateTimeFormatter.ofPattern("HH:mm:ss");

    private final ChatBuffer buffer;
    private final BridgePlayer bridgePlayer;

    public ChatCaptureListener(ChatBuffer buffer, BridgePlayer bridgePlayer) {
        this.buffer = buffer;
        this.bridgePlayer = bridgePlayer;
    }

    @Subscribe
    public void onChatReceive(ChatReceiveEvent event) {
        capture(event.chatMessage());
    }

    @Subscribe
    public void onChatMessageAdd(ChatMessageAddEvent event) {
        capture(event.chatMessage());
    }

    private void capture(ChatMessage message) {
        if (message == null || message.wasDeleted()) {
            return;
        }

        String senderNick = null;
        GameProfile profile = message.getSenderProfile();
        if (profile != null) {
            senderNick = profile.getUsername();
        }

        ChatMessageParser.ParsedMessage parsed = null;
        String[] candidates = textCandidates(message);
        for (String raw : candidates) {
            parsed = ChatMessageParser.parseWithSender(raw, senderNick);
            if (parsed != null) {
                break;
            }
        }
        if (parsed == null) {
            return;
        }

        boolean alteredNick = parsed.alteredNick();
        if (!alteredNick) {
            for (String raw : candidates) {
                if (ChatMessageParser.hasAlteredNickPrefix(raw, parsed.nickname())) {
                    alteredNick = true;
                    break;
                }
            }
        }
        if (!alteredNick && this.bridgePlayer != null && this.bridgePlayer.isInWorld()) {
            alteredNick = this.bridgePlayer.hasAlteredNickDisplay(parsed.nickname());
        }

        String timestamp = LocalTime.now().format(TIME_FORMAT);
        this.buffer.pushIfNew(
            message.messageId(),
            timestamp,
            parsed.nickname(),
            parsed.text(),
            alteredNick
        );
    }

    private static String[] textCandidates(ChatMessage message) {
        return new String[] {
            message.getOriginalPlainText(),
            message.getPlainText(),
            message.getOriginalFormattedText(),
            message.getFormattedText(),
        };
    }
}
