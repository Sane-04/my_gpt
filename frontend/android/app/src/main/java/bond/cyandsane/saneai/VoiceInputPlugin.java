package bond.cyandsane.saneai;

import android.Manifest;
import android.annotation.SuppressLint;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.util.Log;

import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;
import com.iflytek.sparkchain.core.SparkChain;
import com.iflytek.sparkchain.core.SparkChainConfig;
import com.iflytek.sparkchain.core.asr.ASR;
import com.iflytek.sparkchain.core.asr.AsrCallbacks;

import java.io.File;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicBoolean;

@CapacitorPlugin(
    name = "VoiceInput",
    permissions = {
        @Permission(strings = { Manifest.permission.RECORD_AUDIO }, alias = VoiceInputPlugin.MICROPHONE_PERMISSION)
    }
)
public class VoiceInputPlugin extends Plugin {
    private static final String TAG = "VoiceInputPlugin";
    static final String MICROPHONE_PERMISSION = "microphone";
    private static final int SAMPLE_RATE = 16000;
    private static final int FRAME_BYTES = 1280;
    private static final int MIN_RECORD_DURATION_MS = 500;

    private final Object sessionLock = new Object();
    private final AtomicBoolean isRecording = new AtomicBoolean(false);
    private final AtomicBoolean shouldDiscardResult = new AtomicBoolean(false);
    private final AtomicBoolean hasFinalResultEmitted = new AtomicBoolean(false);
    private ASR asr;
    private AudioRecord audioRecord;
    private Thread recordingThread;
    private boolean initialized = false;
    private long recordingStartedAtMs = 0L;
    private final StringBuilder resultBuffer = new StringBuilder();

    private final AsrCallbacks asrCallbacks = new AsrCallbacks() {
        @Override
        public void onResult(ASR.ASRResult asrResult, Object usrTag) {
            String text = asrResult.getBestMatchText();
            int status = asrResult.getStatus();
            String sid = asrResult.getSid();

            if (text != null && !text.trim().isEmpty()) {
                synchronized (resultBuffer) {
                    mergeRecognizedText(text.trim());
                }
            }

            String currentText = getCurrentResultText();
            JSObject partial = new JSObject();
            partial.put("text", currentText);
            partial.put("status", status);
            partial.put("sid", sid);
            notifyListeners("partialResult", partial);

            if (status == 2) {
                finishSessionWithFinalResult(sid);
            }
        }

        @Override
        public void onError(ASR.ASRError asrError, Object usrTag) {
            int code = asrError.getCode();
            String message = asrError.getErrMsg();
            String sid = asrError.getSid();
            releaseCurrentSession(false);
            emitError(code, normalizeErrorMessage(code, message), sid);
        }

        @Override
        public void onBeginOfSpeech() {
            emitState("recording");
        }

        @Override
        public void onEndOfSpeech() {
            emitState("stopping");
        }
    };

    /** 函数作用：查询麦克风权限；输入参数：call - Capacitor 调用；输出参数：通过 call.resolve 返回权限状态。 */
    @PluginMethod
    public void checkPermissions(PluginCall call) {
        JSObject result = new JSObject();
        result.put(MICROPHONE_PERMISSION, getPermissionState(MICROPHONE_PERMISSION).toString().toLowerCase(Locale.ROOT));
        call.resolve(result);
    }

    /** 函数作用：请求麦克风权限；输入参数：call - Capacitor 调用；输出参数：通过 call.resolve 返回权限状态。 */
    @PluginMethod
    public void requestPermissions(PluginCall call) {
        if (getPermissionState(MICROPHONE_PERMISSION) == PermissionState.GRANTED) {
            checkPermissions(call);
            return;
        }

        requestPermissionForAlias(MICROPHONE_PERMISSION, call, "microphonePermissionCallback");
    }

    /** 函数作用：处理麦克风权限请求结果；输入参数：call - 原始 Capacitor 调用；输出参数：通过 call.resolve 返回权限状态。 */
    @PermissionCallback
    private void microphonePermissionCallback(PluginCall call) {
        checkPermissions(call);
    }

    /** 函数作用：初始化 SparkChain SDK；输入参数：call - 可选覆盖讯飞凭证；输出参数：初始化结果。 */
    @PluginMethod
    public void initialize(PluginCall call) {
        if (initialized) {
            JSObject result = new JSObject();
            result.put("initialized", true);
            call.resolve(result);
            return;
        }

        String appId = getConfigValue(call, "appId", BuildConfig.XUNFEI_APP_ID);
        String apiKey = getConfigValue(call, "apiKey", BuildConfig.XUNFEI_API_KEY);
        String apiSecret = getConfigValue(call, "apiSecret", BuildConfig.XUNFEI_API_SECRET);

        if (appId.isEmpty() || apiKey.isEmpty() || apiSecret.isEmpty()) {
            call.reject("语音服务未配置");
            return;
        }

        File workDir = new File(getContext().getFilesDir(), "sparkchain");
        if (!workDir.exists() && !workDir.mkdirs()) {
            call.reject("无法创建语音服务工作目录");
            return;
        }

        SparkChainConfig config = SparkChainConfig.builder()
            .appID(appId)
            .apiKey(apiKey)
            .apiSecret(apiSecret)
            .workDir(workDir.getAbsolutePath());
        int initCode = SparkChain.getInst().init(getContext().getApplicationContext(), config);
        initialized = initCode == 0;

        if (!initialized) {
            call.reject("语音服务初始化失败：" + initCode);
            return;
        }

        JSObject result = new JSObject();
        result.put("initialized", true);
        call.resolve(result);
    }

    /** 函数作用：开始语音听写；输入参数：call - 识别语言、领域和方言参数；输出参数：启动结果。 */
    @SuppressLint("MissingPermission")
    @PluginMethod
    public void startListening(PluginCall call) {
        if (getPermissionState(MICROPHONE_PERMISSION) != PermissionState.GRANTED) {
            call.reject("需要麦克风权限才能语音输入");
            return;
        }

        if (isRecording.get()) {
            call.reject("正在语音输入中");
            return;
        }

        if (!initialized) {
            initializeForListening(call);
            if (!initialized) {
                return;
            }
        }

        synchronized (sessionLock) {
            shouldDiscardResult.set(false);
            hasFinalResultEmitted.set(false);
            resultBuffer.setLength(0);
            asr = new ASR(
                call.getString("language", "zh_cn"),
                call.getString("domain", "iat"),
                call.getString("accent", "henanese")
            );
            asr.ptt(true);
            asr.vadEos(call.getInt("vadEos", 8000));
            asr.registerCallbacks(asrCallbacks);

            int startCode = asr.start("voice-input-" + System.currentTimeMillis());
            if (startCode != 0) {
                asr = null;
                call.reject("识别开启失败：" + startCode);
                return;
            }

            int minBufferSize = AudioRecord.getMinBufferSize(
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT
            );
            int bufferSize = Math.max(minBufferSize, FRAME_BYTES * 2);
            audioRecord = new AudioRecord(
                MediaRecorder.AudioSource.MIC,
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                bufferSize
            );

            if (audioRecord.getState() != AudioRecord.STATE_INITIALIZED) {
                releaseCurrentSession(true);
                call.reject("无法启动录音");
                return;
            }

            isRecording.set(true);
            recordingStartedAtMs = System.currentTimeMillis();
            audioRecord.startRecording();
            recordingThread = new Thread(this::recordAndWriteAudio, "voice-input-recorder");
            recordingThread.start();
        }

        emitState("recording");
        JSObject result = new JSObject();
        result.put("started", true);
        call.resolve(result);
    }

    /** 函数作用：停止语音听写并等待最终结果；输入参数：call - Capacitor 调用；输出参数：停止请求结果。 */
    @PluginMethod
    public void stopListening(PluginCall call) {
        long duration = System.currentTimeMillis() - recordingStartedAtMs;
        if (duration < MIN_RECORD_DURATION_MS) {
            releaseCurrentSession(true);
            emitError(0, "说话时间太短", null);
            JSObject result = new JSObject();
            result.put("stopping", false);
            call.resolve(result);
            return;
        }

        stopRecorderOnly();
        ASR currentAsr;
        synchronized (sessionLock) {
            currentAsr = asr;
        }
        if (currentAsr != null) {
            currentAsr.stop(false);
        }

        emitState("stopping");
        JSObject result = new JSObject();
        result.put("stopping", true);
        call.resolve(result);
    }

    /** 函数作用：取消本次语音听写并丢弃结果；输入参数：call - Capacitor 调用；输出参数：取消结果。 */
    @PluginMethod
    public void cancelListening(PluginCall call) {
        releaseCurrentSession(true);
        emitState("cancelled");
        JSObject result = new JSObject();
        result.put("cancelled", true);
        call.resolve(result);
    }

    /** 函数作用：插件销毁时释放录音和识别资源；输入参数：无；输出参数：无返回值。 */
    @Override
    protected void handleOnDestroy() {
        releaseCurrentSession(true);
        super.handleOnDestroy();
    }

    /** 函数作用：读取插件调用或 BuildConfig 中的配置值；输入参数：call、key、fallback；输出参数：配置字符串。 */
    private String getConfigValue(PluginCall call, String key, String fallback) {
        String value = call.getString(key);
        if (value == null || value.trim().isEmpty()) {
            return fallback == null ? "" : fallback.trim();
        }
        return value.trim();
    }

    /** 函数作用：为 startListening 初始化 SDK；输入参数：call - 原始调用；输出参数：初始化失败时会 reject。 */
    private void initializeForListening(PluginCall call) {
        String appId = BuildConfig.XUNFEI_APP_ID == null ? "" : BuildConfig.XUNFEI_APP_ID.trim();
        String apiKey = BuildConfig.XUNFEI_API_KEY == null ? "" : BuildConfig.XUNFEI_API_KEY.trim();
        String apiSecret = BuildConfig.XUNFEI_API_SECRET == null ? "" : BuildConfig.XUNFEI_API_SECRET.trim();
        if (appId.isEmpty() || apiKey.isEmpty() || apiSecret.isEmpty()) {
            call.reject("语音服务未配置");
            return;
        }

        File workDir = new File(getContext().getFilesDir(), "sparkchain");
        if (!workDir.exists() && !workDir.mkdirs()) {
            call.reject("无法创建语音服务工作目录");
            return;
        }

        SparkChainConfig config = SparkChainConfig.builder()
            .appID(appId)
            .apiKey(apiKey)
            .apiSecret(apiSecret)
            .workDir(workDir.getAbsolutePath());
        int initCode = SparkChain.getInst().init(getContext().getApplicationContext(), config);
        initialized = initCode == 0;
        if (!initialized) {
            call.reject("语音服务初始化失败：" + initCode);
        }
    }

    /** 函数作用：录音线程读取 PCM 并送入讯飞 ASR；输入参数：无；输出参数：无返回值。 */
    private void recordAndWriteAudio() {
        byte[] buffer = new byte[FRAME_BYTES];
        while (isRecording.get()) {
            AudioRecord currentRecorder = audioRecord;
            ASR currentAsr = asr;
            if (currentRecorder == null || currentAsr == null) {
                break;
            }

            int readSize = currentRecorder.read(buffer, 0, buffer.length);
            if (readSize <= 0) {
                continue;
            }

            byte[] frame = new byte[readSize];
            System.arraycopy(buffer, 0, frame, 0, readSize);
            int writeCode = currentAsr.write(frame);
            emitVolume(frame, readSize);
            if (writeCode != 0) {
                Log.w(TAG, "ASR write failed: " + writeCode);
                emitError(writeCode, "识别音频写入失败", null);
                releaseCurrentSession(true);
                break;
            }
        }
    }

    /** 函数作用：仅停止本地录音；输入参数：无；输出参数：无返回值。 */
    private void stopRecorderOnly() {
        isRecording.set(false);
        AudioRecord currentRecorder = audioRecord;
        if (currentRecorder != null) {
            try {
                if (currentRecorder.getRecordingState() == AudioRecord.RECORDSTATE_RECORDING) {
                    currentRecorder.stop();
                }
            } catch (IllegalStateException exception) {
                Log.w(TAG, "Stop recorder failed", exception);
            }
            currentRecorder.release();
            audioRecord = null;
        }
    }

    /** 函数作用：释放当前语音会话；输入参数：discard - 是否丢弃识别结果；输出参数：无返回值。 */
    private void releaseCurrentSession(boolean discard) {
        shouldDiscardResult.set(discard);
        stopRecorderOnly();
        synchronized (sessionLock) {
            if (asr != null && discard) {
                asr.stop(true);
            }
            asr = null;
        }
        recordingThread = null;
    }

    /** 函数作用：完成最终结果回传；输入参数：sid - 讯飞会话 ID；输出参数：无返回值。 */
    private void finishSessionWithFinalResult(String sid) {
        if (hasFinalResultEmitted.getAndSet(true)) {
            return;
        }

        String text = getCurrentResultText();
        boolean discard = shouldDiscardResult.get();
        releaseCurrentSession(discard);
        if (discard) {
            return;
        }

        JSObject result = new JSObject();
        result.put("text", text);
        result.put("sid", sid);
        notifyListeners("finalResult", result);
        emitState("idle");
    }

    /** 函数作用：读取当前累计识别文本；输入参数：无；输出参数：识别文本。 */
    private String getCurrentResultText() {
        synchronized (resultBuffer) {
            return resultBuffer.toString().trim();
        }
    }

    /** 函数作用：合并讯飞多次回调文本并去掉重复重叠内容；输入参数：text 本次识别文本；输出参数：无返回值。 */
    private void mergeRecognizedText(String text) {
        if (text.isEmpty()) {
            return;
        }

        String currentText = resultBuffer.toString();
        if (currentText.isEmpty()) {
            resultBuffer.append(text);
            return;
        }

        if (currentText.equals(text) || currentText.endsWith(text)) {
            return;
        }

        if (text.startsWith(currentText)) {
            resultBuffer.setLength(0);
            resultBuffer.append(text);
            return;
        }

        int maxOverlap = Math.min(currentText.length(), text.length());
        for (int overlap = maxOverlap; overlap > 0; overlap--) {
            if (currentText.regionMatches(currentText.length() - overlap, text, 0, overlap)) {
                resultBuffer.append(text.substring(overlap));
                return;
            }
        }

        resultBuffer.append(text);
    }

    /** 函数作用：根据 PCM 音频粗略计算音量等级并通知前端；输入参数：data 音频帧、size 帧长度；输出参数：无返回值。 */
    private void emitVolume(byte[] data, int size) {
        long sum = 0L;
        int samples = 0;
        for (int index = 0; index + 1 < size; index += 2) {
            int sample = (data[index] & 0xff) | (data[index + 1] << 8);
            sum += Math.abs(sample);
            samples++;
        }

        int level = 0;
        if (samples > 0) {
            level = Math.min(100, (int) ((sum / samples) / 128));
        }
        JSObject payload = new JSObject();
        payload.put("level", level);
        notifyListeners("volumeChanged", payload);
    }

    /** 函数作用：通知前端原生语音状态变化；输入参数：state 状态名；输出参数：无返回值。 */
    private void emitState(String state) {
        JSObject payload = new JSObject();
        payload.put("state", state);
        notifyListeners("stateChanged", payload);
    }

    /** 函数作用：通知前端语音错误；输入参数：code 错误码、message 错误信息、sid 会话 ID；输出参数：无返回值。 */
    private void emitError(int code, String message, String sid) {
        JSObject payload = new JSObject();
        payload.put("code", code);
        payload.put("message", message);
        if (sid != null) {
            payload.put("sid", sid);
        }
        notifyListeners("voiceError", payload);
    }

    /** 函数作用：把讯飞错误整理为用户可读文案；输入参数：code 错误码、message 原始错误；输出参数：中文错误提示。 */
    private String normalizeErrorMessage(int code, String message) {
        if (code == 10005 || code == 11200 || code == 18007 || code == 18705) {
            return "语音服务授权失败，请检查配置";
        }
        if (message == null || message.trim().isEmpty()) {
            return "识别失败，请稍后重试";
        }
        return message;
    }
}
