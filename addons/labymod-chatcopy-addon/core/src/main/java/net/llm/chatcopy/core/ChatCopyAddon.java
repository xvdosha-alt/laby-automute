package net.llm.chatcopy.core;

import net.labymod.api.addon.LabyAddon;
import net.labymod.api.models.addon.annotation.AddonMain;

@AddonMain
public class ChatCopyAddon extends LabyAddon<ChatCopyConfiguration> {

    @Override
    protected void enable() {
        ChatAnimationDisabler.apply();
        this.registerListener(new ChatFadeGuard());
        this.registerListener(new ChatCopyListener());
        this.logger().info("Chat Copy enabled — [copy] button on chat lines");
    }

    @Override
    protected Class<ChatCopyConfiguration> configurationClass() {
        return ChatCopyConfiguration.class;
    }
}
