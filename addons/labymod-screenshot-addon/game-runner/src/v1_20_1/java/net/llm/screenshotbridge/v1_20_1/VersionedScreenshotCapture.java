package net.llm.screenshotbridge.v1_20_1;

import com.mojang.blaze3d.platform.NativeImage;
import com.mojang.blaze3d.pipeline.RenderTarget;
import java.awt.image.BufferedImage;
import java.io.File;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import javax.imageio.ImageIO;
import net.labymod.api.models.Implements;
import net.llm.screenshotbridge.api.ScreenshotCapture;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;

@Implements(ScreenshotCapture.class)
public class VersionedScreenshotCapture implements ScreenshotCapture {

    private static final long CAPTURE_TIMEOUT_SECONDS = 5;

    @Override
    public boolean isInWorld() {
        Minecraft minecraft = Minecraft.getInstance();
        return minecraft != null && minecraft.level != null;
    }

    @Override
    public void setPauseOnLostFocus(boolean enabled) {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft != null) {
            minecraft.options.pauseOnLostFocus = enabled;
        }
    }

    @Override
    public CaptureResult capture(String path, String format) throws Exception {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft == null) {
            throw new IllegalStateException("minecraft_unavailable");
        }

        CompletableFuture<CaptureResult> future = new CompletableFuture<>();

        Runnable captureTask = () -> {
            Runnable restoreChat = null;
            try {
                if (minecraft.level == null) {
                    future.completeExceptionally(new IllegalStateException("not_in_world"));
                    return;
                }

                restoreChat = ChatScreenshotHelper.prepare(minecraft);

                RenderTarget framebuffer = minecraft.getMainRenderTarget();
                NativeImage nativeImage = Screenshot.takeScreenshot(framebuffer);
                try {
                    File output = new File(path);
                    File parent = output.getParentFile();
                    if (parent != null) {
                        parent.mkdirs();
                    }

                    String normalizedFormat = format.toLowerCase();
                    if ("jpg".equals(normalizedFormat) || "jpeg".equals(normalizedFormat)) {
                        writeJpeg(nativeImage, output);
                    } else {
                        nativeImage.writeToFile(output);
                    }

                    future.complete(new CaptureResult(
                        output.getAbsolutePath(),
                        nativeImage.getWidth(),
                        nativeImage.getHeight()
                    ));
                } finally {
                    nativeImage.close();
                }
            } catch (Exception e) {
                future.completeExceptionally(e);
            } finally {
                if (restoreChat != null) {
                    restoreChat.run();
                }
            }
        };

        if (minecraft.isSameThread()) {
            captureTask.run();
        } else {
            minecraft.execute(captureTask);
        }

        try {
            return future.get(CAPTURE_TIMEOUT_SECONDS, TimeUnit.SECONDS);
        } catch (TimeoutException e) {
            throw new IllegalStateException("capture_timeout");
        }
    }

    private static void writeJpeg(NativeImage nativeImage, File output) throws Exception {
        int width = nativeImage.getWidth();
        int height = nativeImage.getHeight();
        BufferedImage bufferedImage = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);

        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                int pixel = nativeImage.getPixelRGBA(x, y);
                int red = pixel & 0xFF;
                int green = (pixel >> 8) & 0xFF;
                int blue = (pixel >> 16) & 0xFF;
                bufferedImage.setRGB(x, y, (red << 16) | (green << 8) | blue);
            }
        }

        ImageIO.write(bufferedImage, "jpg", output);
    }
}
