package com.baba.callvault.services.recording.handoff

import android.os.ParcelFileDescriptor
import com.baba.callvault.utils.AppLogger
import java.io.InputStream
import java.io.OutputStream

/**
 * Reads from a single source InputStream and duplicates the PCM bytes to multiple OutputStreams.
 * Useful for teeing the native handoff pipe to both the local file encoder and the network sink.
 */
class PcmTee(
    private val source: InputStream,
    private val destinations: List<OutputStream>
) {
    private val T = "CV:PcmTee"

    fun startBlocking() {
        val buffer = ByteArray(8192)
        try {
            while (true) {
                val read = source.read(buffer)
                if (read == -1) break
                
                for (dest in destinations) {
                    try {
                        dest.write(buffer, 0, read)
                    } catch (e: Exception) {
                        // Ignore write errors to individual destinations (e.g. one pipe closed early)
                    }
                }
            }
        } catch (e: Exception) {
            AppLogger.w(T, "Tee read error: ${e.message}")
        } finally {
            // Close source
            runCatching { source.close() }
            
            // Close all destinations
            for (dest in destinations) {
                runCatching { dest.close() }
            }
            AppLogger.i(T, "Tee finished and closed all streams")
        }
    }
}
