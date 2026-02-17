package com.speaknode.client.util

/**
 * Utility for decoding scoped values in the SpeakNode graph.
 * Scoped values follow the format: "meeting_id::plain_text"
 */
object ScopeUtils {
    /** Decode "meeting_id::some text" → "some text". Returns original if no scope. */
    fun decode(value: String): String {
        val idx = value.indexOf("::")
        return if (idx >= 0) value.substring(idx + 2) else value
    }

    /** Extract the scope (meeting_id) from a scoped value, or null. */
    fun extractScope(value: String): String? {
        val idx = value.indexOf("::")
        return if (idx >= 0) value.substring(0, idx) else null
    }
}
