package net.llm.screenshotbridge.v1_20_1.mixins;

import net.llm.screenshotbridge.core.CutdownModeState;
import net.llm.screenshotbridge.v1_20_1.VersionedCutdownModeController;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientChunkCache;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.ModifyVariable;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(ClientChunkCache.class)
public class MixinClientChunkCache {

    @ModifyVariable(method = "updateViewRadius", at = @At("HEAD"), argsOnly = true)
    private int screenshotbridge$clampViewRadius(int radius) {
        if (!CutdownModeState.isActive()) {
            return radius;
        }
        return Math.min(radius, CutdownModeState.getChunkKeepRadius());
    }

    @Inject(method = "tick", at = @At("HEAD"))
    private void screenshotbridge$trimLoadedChunks(java.util.function.BooleanSupplier hasTimeLeft, boolean tickChunks, CallbackInfo ci) {
        if (!CutdownModeState.isActive() || !tickChunks) {
            return;
        }

        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.player == null) {
            return;
        }

        int centerX = minecraft.player.chunkPosition().x;
        int centerZ = minecraft.player.chunkPosition().z;
        VersionedCutdownModeController.dropDistantChunks(
            (ClientChunkCache) (Object) this,
            centerX,
            centerZ,
            CutdownModeState.getChunkKeepRadius()
        );
    }
}
