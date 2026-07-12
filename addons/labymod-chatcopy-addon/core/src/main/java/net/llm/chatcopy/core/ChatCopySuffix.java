package net.llm.chatcopy.core;

import java.util.Collections;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import net.labymod.api.client.chat.ChatMessage;
import net.labymod.api.client.component.Component;
import net.labymod.api.client.component.event.ClickEvent;
import net.labymod.api.client.component.format.TextColor;

public final class ChatCopySuffix {

    static final String METADATA_KEY = "chatcopy_suffix";
    private static final int MAX_TRACKED_IDS = 512;

    private static final TextColor BRACKET_COLOR = TextColor.color(255, 255, 255);
    private static final TextColor COPY_COLOR = TextColor.color(124, 252, 0);
    private static final Set<UUID> PROCESSED_IDS = Collections.newSetFromMap(new ConcurrentHashMap<>());

    private ChatCopySuffix() {
    }

    public static boolean alreadyAppended(ChatMessage message) {
        if (message == null) {
            return false;
        }
        if (message.metadata().has(METADATA_KEY)) {
            return true;
        }
        UUID messageId = message.messageId();
        return messageId != null && PROCESSED_IDS.contains(messageId);
    }

    public static void markAppended(ChatMessage message) {
        if (message == null) {
            return;
        }
        message.metadata().set(METADATA_KEY, true);
        UUID messageId = message.messageId();
        if (messageId == null) {
            return;
        }
        PROCESSED_IDS.add(messageId);
        while (PROCESSED_IDS.size() > MAX_TRACKED_IDS) {
            PROCESSED_IDS.remove(PROCESSED_IDS.iterator().next());
        }
    }

    public static Component withCopyButton(Component messageComponent, ChatMessage message) {
        String clipboardText = clipboardText(message);
        Component copyButton = Component.text(" ", BRACKET_COLOR)
            .append(Component.text("[", BRACKET_COLOR))
            .append(Component.text("copy", COPY_COLOR)
                .clickEvent(ClickEvent.copyToClipboard(clipboardText)))
            .append(Component.text("]", BRACKET_COLOR));
        return messageComponent.copy().append(copyButton);
    }

    public static String clipboardText(ChatMessage message) {
        if (message == null) {
            return "";
        }

        for (String candidate : new String[] {
            message.getOriginalPlainText(),
            message.getPlainText(),
            message.getOriginalFormattedText(),
            message.getFormattedText(),
        }) {
            String cleaned = stripFormatting(candidate);
            if (!cleaned.isBlank()) {
                return cleaned;
            }
        }
        return "";
    }

    private static String stripFormatting(String text) {
        if (text == null) {
            return "";
        }
        StringBuilder out = new StringBuilder(text.length());
        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            if (ch == '\u00A7' && i + 1 < text.length()) {
                i++;
                continue;
            }
            out.append(ch);
        }
        return out.toString().trim();
    }
}
