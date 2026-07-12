package net.llm.screenshotbridge.v1_20_1.mixins;

import net.llm.screenshotbridge.core.CutdownModeState;
import net.minecraft.client.renderer.chunk.ChunkRenderDispatcher;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(ChunkRenderDispatcher.class)
public class MixinChunkRenderDispatcher {

    @Inject(method = "schedule", at = @At("HEAD"), cancellable = true)
    private void screenshotbridge$skipChunkMeshBuild(CallbackInfo ci) {
        if (CutdownModeState.isActive()) {
            ci.cancel();
        }
    }
}
