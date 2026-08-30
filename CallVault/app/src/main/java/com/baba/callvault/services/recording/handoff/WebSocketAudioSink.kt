package com.baba.callvault.services.recording.handoff

import com.baba.callvault.utils.AppLogger
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import java.io.InputStream
import java.util.concurrent.TimeUnit

/**
 * Connects to the Media Gateway via WebSocket and streams raw PCM.
 * Adheres to the gateway protocol (session.start -> binary chunks -> session.stop).
 */
class WebSocketAudioSink(
    private val url: String,
    private val sessionId: String,
    private val sampleRate: Int,
    private val channels: Int
) {
    private val T = "CV:WsSink"
    private var webSocket: WebSocket? = null
    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .build()

    fun connect() {
        val request = Request.Builder().url(url).build()
        val listener = object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                android.util.Log.i(T, "WebSocket connected. Sending session.start")
                val startMsg = JSONObject().apply {
                    put("type", "session.start")
                    put("session_id", sessionId)
                    put("source", "CallVault")
                    put("sample_rate", sampleRate)
                    put("channels", channels)
                    put("encoding", "pcm_s16le")
                }
                webSocket.send(startMsg.toString())
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                android.util.Log.e(T, "WebSocket failure: ${t.message}", t)
            }
        }

        webSocket = client.newWebSocket(request, listener)
    }

    fun sendPcm(pcm: ByteArray, len: Int) {
        if (len <= 0) return
        webSocket?.send(pcm.copyOfRange(0, len).toByteString())
    }

    fun close() {
        android.util.Log.i(T, "PCM stream ended. Sending session.stop")
        val stopMsg = JSONObject().apply {
            put("type", "session.stop")
            put("session_id", sessionId)
        }
        webSocket?.send(stopMsg.toString())
        webSocket?.close(1000, "EOF")
    }
}
