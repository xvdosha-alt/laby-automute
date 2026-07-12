package net.llm.screenshotbridge.core;

import net.labymod.api.Laby;

public final class ChatAnimationDisabler {

    private ChatAnimationDisabler() {
    }

    public static void apply() {
        if (!Laby.isInitialized()) {
            return;
        }

        try {
            Laby.labyAPI()
                .config()
                .ingame()
                .advancedChat()
                .fadeInMessages()
                .set(false);
        } catch (Exception ignored) {
            // LabyMod chat config may not be ready yet.
        }
    }
}
