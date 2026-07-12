package net.llm.screenshotbridge.api;

import net.labymod.api.reference.annotation.Referenceable;

@Referenceable
public interface CutdownModeController {

    boolean isInWorld();

    void captureFrozenPose();

    void applyMemoryCuts();

    void restoreMemorySettings();

    void notifyToggled(boolean enabled);
}
