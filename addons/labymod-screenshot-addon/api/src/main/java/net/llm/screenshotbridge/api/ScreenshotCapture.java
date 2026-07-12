package net.llm.screenshotbridge.api;

import net.labymod.api.reference.annotation.Referenceable;

@Referenceable
public interface ScreenshotCapture {

    record CaptureResult(String path, int width, int height) {
    }

    CaptureResult capture(String path, String format) throws Exception;

    boolean isInWorld();

    void setPauseOnLostFocus(boolean enabled);
}
