package net.llm.chatcopy.core;

import java.util.function.Consumer;
import net.labymod.api.client.chat.ChatMessage;
import net.labymod.api.client.component.Component;
import net.labymod.api.configuration.labymod.chat.AdvancedChatMessage;
import net.labymod.api.event.Subscribe;
import net.labymod.api.event.client.chat.ChatReceiveEvent;
import net.labymod.api.event.client.chat.advanced.AdvancedChatTabMessageEvent;

public class ChatCopyListener {

    @Subscribe((byte) 127)
    public void onAdvancedChatTabMessage(AdvancedChatTabMessageEvent event) {
        AdvancedChatMessage advancedMessage = event.message();
        if (advancedMessage == null) {
            return;
        }

        ChatMessage chatMessage = advancedMessage.chatMessage();
        if (chatMessage == null || chatMessage.wasDeleted()) {
            return;
        }
        if (ChatCopySuffix.alreadyAppended(chatMessage)) {
            return;
        }

        append(event.component(), chatMessage, event::setMessage);
    }

    @Subscribe((byte) 127)
    public void onChatReceive(ChatReceiveEvent event) {
        ChatMessage chatMessage = event.chatMessage();
        if (chatMessage == null || chatMessage.wasDeleted()) {
            return;
        }
        if (ChatCopySuffix.alreadyAppended(chatMessage)) {
            return;
        }

        append(event.message(), chatMessage, event::setMessage);
    }

    private static void append(
        Component current,
        ChatMessage chatMessage,
        Consumer<Component> sink
    ) {
        if (current == null) {
            return;
        }

        String clipboard = ChatCopySuffix.clipboardText(chatMessage);
        if (clipboard.isBlank()) {
            return;
        }

        sink.accept(ChatCopySuffix.withCopyButton(current, chatMessage));
        ChatCopySuffix.markAppended(chatMessage);
    }
}
