from neurosync_driver import NeuroSyncDriver

if __name__ == "__main__":
    driver = NeuroSyncDriver()
    driver.sync_loop()