import { AnimatePresence, motion } from "framer-motion";
import { TitleBar } from "./components/TitleBar";
import { BottomBar } from "./components/BottomBar";
import { CameraView } from "./components/CameraView";
import { Library } from "./components/Library";
import { SettingsSheet } from "./components/SettingsSheet";
import { SetupSheet } from "./components/SetupSheet";
import { ProcessingPane } from "./components/ProcessingPane";
import { AppProvider, useApp } from "./state";

function Shell() {
  const { mode } = useApp();
  return (
    <div className="h-full flex flex-col bg-paper text-ink">
      <TitleBar />
      <AnimatePresence mode="wait">
        {mode === "camera" ? (
          <motion.main
            key="camera"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
            className="flex-1 flex min-h-0"
          >
            <CameraView />
          </motion.main>
        ) : (
          <motion.main
            key="library"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
            className="flex-1 flex min-h-0"
          >
            <Library />
          </motion.main>
        )}
      </AnimatePresence>
      <BottomBar />
      <SetupSheet />
      <SettingsSheet />
      <ProcessingPane />
    </div>
  );
}

export function App() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  );
}
