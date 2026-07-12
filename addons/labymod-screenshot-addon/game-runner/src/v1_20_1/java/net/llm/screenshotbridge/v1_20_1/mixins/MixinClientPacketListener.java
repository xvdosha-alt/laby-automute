package net.llm.screenshotbridge.v1_20_1.mixins;

import net.llm.screenshotbridge.core.CutdownModeState;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientPacketListener;
import net.minecraft.network.protocol.game.ClientboundLevelChunkWithLightPacket;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(ClientPacketListener.class)
public class MixinClientPacketListener {

    @Inject(method = "handleLevelChunkWithLight", at = @At("HEAD"), cancellable = true)
    private void screenshotbridge$skipDistantChunkPacket(
        ClientboundLevelChunkWithLightPacket packet,
        CallbackInfo ci
    ) {
        if (!CutdownModeState.isActive()) {
            return;
        }

        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.player == null) {
            return;
        }

        int centerX = minecraft.player.chunkPosition().x;
        int centerZ = minecraft.player.chunkPosition().z;
        int distance = Math.max(Math.abs(packet.getX() - centerX), Math.abs(packet.getZ() - centerZ));
        if (distance > CutdownModeState.getChunkKeepRadius()) {
            ci.cancel();
        }
    }
}
