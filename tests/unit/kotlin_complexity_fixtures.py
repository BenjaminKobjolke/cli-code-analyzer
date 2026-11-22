"""Kotlin source shared by lambda-range regression tests."""

MAIN_ACTIVITY = """class MainActivity {
    fun configureFlutterEngine() {
        pendingOpenFileData?.let { data ->
            if (data != null) {
                println(data)
            }
        }
        println("configured")
    }

    override fun onNewIntent(intent: Intent) {
        if (intent != null) {
            if (intent.data != null) {
                println(intent.data)
            }
        }
    }
}
"""
