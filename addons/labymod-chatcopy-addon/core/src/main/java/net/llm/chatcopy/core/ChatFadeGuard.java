package net.llm.chatcopy.core;

import net.labymod.api.event.Subscribe;
import net.labymod.api.event.client.lifecycle.GameTickEvent;

public class ChatFadeGuard {

    private int ticks;

    @Subscribe
    public void onGameTick(GameTickEvent event) {
        if (++this.ticks < 40) {
            return;
        }
        this.ticks = 0;
        ChatAnimationDisabler.apply();
    }
}
