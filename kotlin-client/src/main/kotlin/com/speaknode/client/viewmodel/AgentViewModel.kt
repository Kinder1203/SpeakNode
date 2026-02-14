package com.speaknode.client.viewmodel

import com.speaknode.client.api.SpeakNodeApi
import com.speaknode.client.api.models.AgentResponse
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * ViewModel managing Agent conversation state.
 *
 * Maintains independent conversation history per chat session.
 */
class AgentViewModel(
    private val api: SpeakNodeApi = SpeakNodeApi(),
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    // Conversation history 
    private val _messages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val messages: StateFlow<List<ChatMessage>> = _messages.asStateFlow()

    // Loading state 
    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    /**
     * Sends a question to the Agent and appends the response to the conversation history.
     */
    fun sendQuery(question: String, chatId: String) {
        val currentMessages = _messages.value.toMutableList()
        currentMessages.add(ChatMessage(role = "user", content = question))
        _messages.value = currentMessages

        scope.launch {
            _isLoading.value = true
            try {
                val response: AgentResponse = api.agentQuery(question, chatId)
                val updated = _messages.value.toMutableList()
                updated.add(ChatMessage(role = "assistant", content = response.answer))
                _messages.value = updated
            } catch (e: Exception) {
                val updated = _messages.value.toMutableList()
                updated.add(ChatMessage(role = "error", content = "오류: ${e.message}"))
                _messages.value = updated
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun clearHistory() {
        _messages.value = emptyList()
    }

    fun dispose() {
        scope.cancel()
        api.close()
    }
}

data class ChatMessage(
    val role: String,   // "user" | "assistant" | "error"
    val content: String,
)
