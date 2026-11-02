package it.fileshare98

import android.app.Activity
import android.content.ContentValues
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.MediaStore
import android.util.Base64
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.ComponentActivity
import java.io.OutputStream

class MainActivity : ComponentActivity() {
    private lateinit var web: WebView
    private var chooserCallback: ValueCallback<Array<Uri>>? = null
    private var output: OutputStream? = null
    private var pendingUri: Uri? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        web = WebView(this)
        web.settings.javaScriptEnabled = true
        web.settings.domStorageEnabled = true
        web.settings.allowFileAccess = true
        web.settings.allowContentAccess = true
        web.webViewClient = WebViewClient()
        web.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(view: WebView?, callback: ValueCallback<Array<Uri>>?, params: FileChooserParams?): Boolean {
                chooserCallback?.onReceiveValue(null)
                chooserCallback = callback
                val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "*/*"
                    putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
                }
                startActivityForResult(intent, FILE_PICKER)
                return true
            }
        }
        web.addJavascriptInterface(AndroidFileBridge(), "AndroidFileBridge")
        setContentView(web)
        web.loadUrl("file:///android_asset/index.html")
    }

    inner class AndroidFileBridge {
        @JavascriptInterface
        fun beginFile(name: String, mime: String, size: Long) {
            try {
                synchronized(this@MainActivity) {
                    output?.close()
                    val values = ContentValues().apply {
                        put(MediaStore.Downloads.DISPLAY_NAME, name.replace(Regex("[\\\\/:*?\"<>|]"), "_"))
                        put(MediaStore.Downloads.MIME_TYPE, mime.ifBlank { "application/octet-stream" })
                        put(MediaStore.Downloads.RELATIVE_PATH, "Download/File Share 98")
                        put(MediaStore.Downloads.IS_PENDING, 1)
                    }
                    pendingUri = contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                    output = pendingUri?.let { contentResolver.openOutputStream(it, "w") }
                    if (output == null) throw IllegalStateException("Impossibile creare il file nei Download")
                }
                runOnUiThread { Toast.makeText(this@MainActivity, "Ricezione: $name", Toast.LENGTH_SHORT).show() }
            } catch (e: Exception) {
                runOnUiThread { Toast.makeText(this@MainActivity, "Errore salvataggio: ${e.message}", Toast.LENGTH_LONG).show() }
            }
        }
        @JavascriptInterface
        fun appendChunk(base64: String) {
            try {
                val bytes = Base64.decode(base64, Base64.DEFAULT)
                synchronized(this@MainActivity) { output?.write(bytes) ?: throw IllegalStateException("File non inizializzato") }
            } catch (e: Exception) {
                runOnUiThread { Toast.makeText(this@MainActivity, "Errore scrittura: ${e.message}", Toast.LENGTH_LONG).show() }
            }
        }

        @JavascriptInterface
        fun finishFile() {
            try {
                synchronized(this@MainActivity) {
                    output?.flush()
                    output?.close()
                    output = null
                    pendingUri?.let { uri ->
                        val values = ContentValues().apply { put(MediaStore.Downloads.IS_PENDING, 0) }
                        contentResolver.update(uri, values, null, null)
                    }
                    pendingUri = null
                }
                runOnUiThread { Toast.makeText(this@MainActivity, "File salvato in Download/File Share 98", Toast.LENGTH_LONG).show() }
            } catch (e: Exception) {
                runOnUiThread { Toast.makeText(this@MainActivity, "Errore finale: ${e.message}", Toast.LENGTH_LONG).show() }
            }
        }
    }

    @Deprecated("Deprecated in Android 13, retained for WebView file chooser compatibility")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == FILE_PICKER) {
            val uris = if (resultCode == Activity.RESULT_OK) {
                data?.clipData?.let { clip -> Array(clip.itemCount) { clip.getItemAt(it).uri } }
                    ?: data?.data?.let { arrayOf(it) }
            } else null
            chooserCallback?.onReceiveValue(uris)
            chooserCallback = null
        }
    }

    override fun onBackPressed() {
        if (::web.isInitialized && web.canGoBack()) web.goBack() else super.onBackPressed()
    }

    companion object { private const val FILE_PICKER = 98 }
}
