package com.studygrid.companion

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class SecretStore(context: Context) {
    private val preferences = context.getSharedPreferences("studygrid_companion", Context.MODE_PRIVATE)

    var serverUrl: String
        get() = preferences.getString("server_url", BuildConfig.DEFAULT_API_URL).orEmpty()
        set(value) = preferences.edit().putString("server_url", value.trim().trimEnd('/')).apply()

    val hasToken: Boolean
        get() = preferences.contains("companion_token")

    fun saveConnection(serverUrl: String, token: String) {
        this.serverUrl = serverUrl
        preferences.edit().putString("companion_token", encrypt(token)).apply()
    }

    fun token(): String? {
        val encrypted = preferences.getString("companion_token", null) ?: return null
        return runCatching { decrypt(encrypted) }.getOrElse {
            preferences.edit().remove("companion_token").apply()
            null
        }
    }

    fun clearConnection() {
        preferences.edit().remove("companion_token").apply()
    }

    private fun key(): SecretKey {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").run {
            init(
                KeyGenParameterSpec.Builder(
                    KEY_ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
                )
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .build(),
            )
            generateKey()
        }
    }

    private fun encrypt(value: String): String {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val encrypted = cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        return listOf(cipher.iv, encrypted).joinToString(":") {
            Base64.encodeToString(it, Base64.NO_WRAP)
        }
    }

    private fun decrypt(value: String): String {
        val (encodedIv, encodedPayload) = value.split(":", limit = 2)
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(
            Cipher.DECRYPT_MODE,
            key(),
            GCMParameterSpec(128, Base64.decode(encodedIv, Base64.NO_WRAP)),
        )
        val clear = cipher.doFinal(Base64.decode(encodedPayload, Base64.NO_WRAP))
        return clear.toString(Charsets.UTF_8)
    }

    private companion object {
        const val KEY_ALIAS = "studygrid_companion_token"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
    }
}
