package com.speaknode.client.util

import kotlinx.serialization.json.*
import java.awt.Color
import java.awt.Font
import java.awt.RenderingHints
import java.awt.image.BufferedImage
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.Base64
import java.util.zip.CRC32
import java.util.zip.Deflater
import java.util.zip.Inflater
import javax.imageio.ImageIO

/**
 * Read/write SpeakNode graph data embedded in PNG tEXt metadata chunks.
 *
 * Format: PNG tEXt chunk with key "speaknode_data_zlib_b64"
 * Value: base64(zlib_compress(json_string))
 */
object PngMetadata {
    private val PNG_SIGNATURE = byteArrayOf(
        0x89.toByte(), 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
    )
    private const val SPEAKNODE_KEY = "speaknode_data_zlib_b64"
    private const val LEGACY_KEY = "speaknode_data"

    /** Read all tEXt chunks from a PNG byte array. */
    fun readTextChunks(bytes: ByteArray): Map<String, String> {
        for (i in PNG_SIGNATURE.indices) {
            require(bytes[i] == PNG_SIGNATURE[i]) { "Not a valid PNG file" }
        }
        val chunks = mutableMapOf<String, String>()
        var offset = 8
        while (offset < bytes.size - 12) {
            val length = readInt(bytes, offset)
            val type = String(bytes, offset + 4, 4, Charsets.ISO_8859_1)
            if (type == "tEXt" && length > 0) {
                val data = bytes.copyOfRange(offset + 8, offset + 8 + length)
                val nullIdx = data.indexOf(0)
                if (nullIdx > 0) {
                    val key = String(data, 0, nullIdx, Charsets.ISO_8859_1)
                    val value = String(data, nullIdx + 1, data.size - nullIdx - 1, Charsets.ISO_8859_1)
                    chunks[key] = value
                }
            }
            if (type == "IEND") break
            offset += 12 + length
        }
        return chunks
    }

    /** Decode SpeakNode data from a PNG file (supports zlib and legacy). */
    fun decode(file: File): JsonObject? = decode(file.readBytes())

    fun decode(bytes: ByteArray): JsonObject? {
        val chunks = readTextChunks(bytes)
        val encoded = chunks[SPEAKNODE_KEY]
        if (encoded != null) {
            val compressed = Base64.getDecoder().decode(encoded)
            val json = String(inflate(compressed), Charsets.UTF_8)
            return Json.parseToJsonElement(json).jsonObject
        }
        val legacy = chunks[LEGACY_KEY]
        if (legacy != null) {
            return Json.parseToJsonElement(legacy).jsonObject
        }
        return null
    }

    /** Create a share-card PNG with embedded SpeakNode graph data. */
    fun createSharePng(
        graphDump: JsonObject,
        analysisResult: JsonObject?,
        topics: List<String> = emptyList(),
        tasks: List<String> = emptyList(),
        stats: Map<String, Int> = emptyMap(),
    ): ByteArray {
        // 1. Render visual card
        val cardImage = renderShareCard(topics, tasks, stats)
        val baos = ByteArrayOutputStream()
        ImageIO.write(cardImage, "PNG", baos)
        val pngBytes = baos.toByteArray()

        // 2. Build bundle
        val bundle = buildJsonObject {
            put("format", "speaknode_graph_bundle_v1")
            if (analysisResult != null) put("analysis_result", analysisResult)
            put("graph_dump", graphDump)
        }

        // 3. Embed metadata
        val jsonBytes = bundle.toString().toByteArray(Charsets.UTF_8)
        val compressed = deflate(jsonBytes)
        val b64 = Base64.getEncoder().encodeToString(compressed)
        return writePngTextChunk(pngBytes, SPEAKNODE_KEY, b64)
    }

    /** Import graph data from a SpeakNode PNG file. Returns (graphDump, analysisResult?). */
    fun importFromPng(file: File): Pair<JsonObject, JsonObject?>? {
        val data = decode(file) ?: return null
        return if (data["format"]?.jsonPrimitive?.content == "speaknode_graph_bundle_v1") {
            val graphDump = data["graph_dump"]?.jsonObject ?: return null
            val analysisResult = data["analysis_result"]?.jsonObject
            graphDump to analysisResult
        } else {
            // Legacy format: data is the analysis result directly
            null
        }
    }

    // ── Internal ──

    private fun renderShareCard(
        topics: List<String>,
        tasks: List<String>,
        stats: Map<String, Int>,
    ): BufferedImage {
        val w = 800
        val h = 480
        val img = BufferedImage(w, h, BufferedImage.TYPE_INT_ARGB)
        val g = img.createGraphics()
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON)
        g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON)

        // Background
        g.color = Color(15, 15, 15)
        g.fillRect(0, 0, w, h)

        // Grid pattern
        g.color = Color(255, 255, 255, 8)
        for (x in 0..w step 20) g.drawLine(x, 0, x, h)
        for (y in 0..h step 20) g.drawLine(0, y, w, y)

        // Header
        g.color = Color(96, 165, 250)
        g.font = Font(Font.SANS_SERIF, Font.BOLD, 28)
        g.drawString("SpeakNode", 24, 44)
        g.color = Color(156, 163, 175)
        g.font = Font(Font.SANS_SERIF, Font.PLAIN, 13)
        g.drawString("Knowledge Graph Share Card", 24, 66)

        // Divider
        g.color = Color(255, 255, 255, 20)
        g.drawLine(24, 80, 776, 80)

        var y = 110

        // Topics
        g.color = Color(34, 197, 94)
        g.font = Font(Font.SANS_SERIF, Font.BOLD, 16)
        g.drawString("Topics", 24, y); y += 22
        g.font = Font(Font.SANS_SERIF, Font.PLAIN, 13)
        g.color = Color(209, 213, 219)
        for (topic in topics.take(6)) {
            g.drawString("  $topic", 36, y); y += 20
        }

        y += 10

        // Tasks
        g.color = Color(245, 158, 11)
        g.font = Font(Font.SANS_SERIF, Font.BOLD, 16)
        g.drawString("Tasks", 24, y); y += 22
        g.font = Font(Font.SANS_SERIF, Font.PLAIN, 13)
        g.color = Color(209, 213, 219)
        for (task in tasks.take(6)) {
            g.drawString("  $task", 36, y); y += 20
        }

        // Stats (right column)
        var sy = 110
        g.color = Color(96, 165, 250)
        g.font = Font(Font.SANS_SERIF, Font.BOLD, 16)
        g.drawString("Statistics", 500, sy); sy += 25
        g.font = Font(Font.SANS_SERIF, Font.PLAIN, 14)
        for ((label, count) in stats) {
            g.color = Color(156, 163, 175)
            g.drawString("$label:", 500, sy)
            g.color = Color(229, 231, 235)
            g.drawString("$count", 620, sy)
            sy += 22
        }

        // Footer
        g.color = Color(75, 85, 99)
        g.font = Font(Font.SANS_SERIF, Font.PLAIN, 11)
        g.drawString("Generated by SpeakNode — Open this PNG in SpeakNode to restore the graph", 24, 460)

        g.dispose()
        return img
    }

    private fun writePngTextChunk(png: ByteArray, key: String, value: String): ByteArray {
        var iendOffset = -1
        var offset = 8
        while (offset < png.size - 12) {
            val length = readInt(png, offset)
            val type = String(png, offset + 4, 4, Charsets.ISO_8859_1)
            if (type == "IEND") { iendOffset = offset; break }
            offset += 12 + length
        }
        require(iendOffset >= 0) { "Invalid PNG: no IEND chunk found" }

        val keyBytes = key.toByteArray(Charsets.ISO_8859_1)
        val valueBytes = value.toByteArray(Charsets.ISO_8859_1)
        val chunkData = ByteArray(keyBytes.size + 1 + valueBytes.size)
        System.arraycopy(keyBytes, 0, chunkData, 0, keyBytes.size)
        chunkData[keyBytes.size] = 0
        System.arraycopy(valueBytes, 0, chunkData, keyBytes.size + 1, valueBytes.size)

        val crc = CRC32()
        crc.update("tEXt".toByteArray(Charsets.ISO_8859_1))
        crc.update(chunkData)

        val out = ByteArrayOutputStream(png.size + chunkData.size + 12)
        out.write(png, 0, iendOffset)
        out.write(intToBytes(chunkData.size))
        out.write("tEXt".toByteArray(Charsets.ISO_8859_1))
        out.write(chunkData)
        out.write(intToBytes(crc.value.toInt()))
        out.write(png, iendOffset, png.size - iendOffset)
        return out.toByteArray()
    }

    private fun deflate(input: ByteArray): ByteArray {
        val deflater = Deflater(9)
        deflater.setInput(input)
        deflater.finish()
        val output = ByteArrayOutputStream()
        val buffer = ByteArray(4096)
        while (!deflater.finished()) {
            val count = deflater.deflate(buffer)
            output.write(buffer, 0, count)
        }
        deflater.end()
        return output.toByteArray()
    }

    private fun inflate(input: ByteArray): ByteArray {
        val inflater = Inflater()
        inflater.setInput(input)
        val output = ByteArrayOutputStream()
        val buffer = ByteArray(4096)
        while (!inflater.finished()) {
            val count = inflater.inflate(buffer)
            output.write(buffer, 0, count)
        }
        inflater.end()
        return output.toByteArray()
    }

    private fun readInt(bytes: ByteArray, offset: Int): Int =
        ((bytes[offset].toInt() and 0xFF) shl 24) or
                ((bytes[offset + 1].toInt() and 0xFF) shl 16) or
                ((bytes[offset + 2].toInt() and 0xFF) shl 8) or
                (bytes[offset + 3].toInt() and 0xFF)

    private fun intToBytes(value: Int): ByteArray =
        byteArrayOf(
            (value ushr 24).toByte(),
            (value ushr 16).toByte(),
            (value ushr 8).toByte(),
            value.toByte(),
        )
}
