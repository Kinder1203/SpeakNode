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

    // Per-chat conversation history
    private val historyMap = mutableMapOf<String, List<ChatMessage>>()
    private var currentChatId: String = "default"

    // Conversation history (for currently active chat)
    private val _messages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val messages: StateFlow<List<ChatMessage>> = _messages.asStateFlow()

    // Loading state 
    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    /**
     * Switch to a different chat session, preserving history.
     */
    fun switchChat(chatId: String) {
        // Save current history
        historyMap[currentChatId] = _messages.value
        // Load new chat's history
        currentChatId = chatId
        _messages.value = historyMap[chatId] ?: emptyList()
    }

    /**
     * Sends a question to the Agent and appends the response to the conversation history.
     */
    fun sendQuery(question: String, chatId: String) {
        // Ensure we're on the right chat
        if (chatId != currentChatId) {
            switchChat(chatId)
        }

        val currentMessages = _messages.value.toMutableList()
        currentMessages.add(ChatMessage(role = "user", content = question))
        _messages.value = currentMessages
        historyMap[chatId] = currentMessages

        scope.launch {
            _isLoading.value = true
            try {
                val response: AgentResponse = api.agentQuery(question, chatId)
                val updated = _messages.value.toMutableList()
                updated.add(ChatMessage(role = "assistant", content = response.answer))
                _messages.value = updated
                historyMap[chatId] = updated
            } catch (e: Exception) {
                val updated = _messages.value.toMutableList()
                updated.add(ChatMessage(role = "error", content = "오류: ${e.message}"))
                _messages.value = updated
                historyMap[chatId] = updated
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun clearHistory() {
        _messages.value = emptyList()
        historyMap[currentChatId] = emptyList()
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
