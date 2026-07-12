package net.llm.screenshotbridge.v1_20_1;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.ChatScreen;
import net.minecraft.client.gui.screens.Screen;

public final class ChatScreenshotHelper {

    private static final int WARMUP_TICKS = 3;

    private ChatScreenshotHelper() {
    }

    public static Runnable prepare(Minecraft minecraft) {
        Screen previous = minecraft.screen;
        boolean openedByUs = !(previous instanceof ChatScreen);
        if (openedByUs) {
            minecraft.setScreen(new ChatScreen(""));
        }

        warmUp(minecraft);

        return () -> {
            if (openedByUs) {
                minecraft.setScreen(previous);
            }
        };
    }

    private static void warmUp(Minecraft minecraft) {
        for (int i = 0; i < WARMUP_TICKS; i++) {
            if (minecraft.screen != null) {
                minecraft.screen.tick();
            }
            minecraft.gui.tick(minecraft.isPaused());
        }
    }
}
