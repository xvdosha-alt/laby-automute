package net.llm.screenshotbridge.v1_20_1.mixins;

import java.util.function.BooleanSupplier;
import net.labymod.api.client.gui.screen.widget.widgets.activity.chat.ChatLineWidget;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(value = ChatLineWidget.class, remap = false)
public abstract class MixinChatLineWidget {

    @Shadow(remap = false)
    public abstract void setForceRendered(BooleanSupplier supplier);

    @Inject(method = "<init>", at = @At("RETURN"), remap = false)
    private void screenshotbridge$disableFade(CallbackInfo ci) {
        this.setForceRendered(() -> true);
    }
}
