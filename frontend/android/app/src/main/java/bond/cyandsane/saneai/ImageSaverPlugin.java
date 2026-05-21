package bond.cyandsane.saneai;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.media.MediaScannerConnection;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;

@CapacitorPlugin(name = "ImageSaver")
public class ImageSaverPlugin extends Plugin {

    @PluginMethod
    public void saveImageToGallery(PluginCall call) {
        String fileName = call.getString("fileName");
        String mimeType = call.getString("mimeType", "image/png");
        String base64Data = call.getString("base64Data");

        if (fileName == null || fileName.trim().isEmpty()) {
            call.reject("文件名不能为空");
            return;
        }

        if (base64Data == null || base64Data.trim().isEmpty()) {
            call.reject("图片数据不能为空");
            return;
        }

        try {
            byte[] imageBytes = Base64.decode(base64Data, Base64.DEFAULT);
            Uri imageUri = Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q
                ? saveModernImage(fileName, mimeType, imageBytes)
                : saveLegacyImage(fileName, mimeType, imageBytes);

            JSObject result = new JSObject();
            result.put("uri", imageUri.toString());
            call.resolve(result);
        } catch (Exception exception) {
            call.reject("保存到相册失败", exception);
        }
    }

    private Uri saveModernImage(String fileName, String mimeType, byte[] imageBytes) throws Exception {
        ContentResolver resolver = getContext().getContentResolver();
        ContentValues values = new ContentValues();
        values.put(MediaStore.Images.Media.DISPLAY_NAME, sanitizeFileName(fileName));
        values.put(MediaStore.Images.Media.MIME_TYPE, mimeType);
        values.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/Sane-AI");
        values.put(MediaStore.Images.Media.IS_PENDING, 1);

        Uri imageUri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
        if (imageUri == null) {
            throw new IllegalStateException("无法创建相册图片记录");
        }

        try (OutputStream outputStream = resolver.openOutputStream(imageUri)) {
            if (outputStream == null) {
                throw new IllegalStateException("无法打开相册写入流");
            }
            outputStream.write(imageBytes);
        }

        values.clear();
        values.put(MediaStore.Images.Media.IS_PENDING, 0);
        resolver.update(imageUri, values, null, null);
        return imageUri;
    }

    private Uri saveLegacyImage(String fileName, String mimeType, byte[] imageBytes) throws Exception {
        File picturesDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PICTURES);
        File appDir = new File(picturesDir, "Sane-AI");
        if (!appDir.exists() && !appDir.mkdirs()) {
            throw new IllegalStateException("无法创建相册目录");
        }

        File imageFile = new File(appDir, sanitizeFileName(fileName));
        try (FileOutputStream outputStream = new FileOutputStream(imageFile)) {
            outputStream.write(imageBytes);
        }

        MediaScannerConnection.scanFile(
            getContext(),
            new String[] { imageFile.getAbsolutePath() },
            new String[] { mimeType },
            null
        );
        return Uri.fromFile(imageFile);
    }

    private String sanitizeFileName(String fileName) {
        return fileName.replaceAll("[\\\\/:*?\"<>|]+", "-").replaceAll("\\s+", "-");
    }
}
