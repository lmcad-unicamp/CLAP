#!/usr/bin/env python

# The MIT License (MIT)
#
# Copyright (c) 2017 Caian Benedicto <caian@ggaunicamp.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

from .LogUtils import log_lines
from .pynvml import *

import os, time, timeit, threading, logging, datetime, traceback, sys

class PerfModule():
    """
    Performance statistics acquisition module for PY-PITZ. The statistics
    are recorded in the SPITZ log, as well as in a file inside ./perf/. The
    file is unique for each SPITZ process.

    Available statistics:
      - Number of compute workers
      - Total wall time (since beginning of PerfModule) [us]
      - Total user time (since beginning of PerfModule) [us]
      - Total system time (since beginning of PerfModule) [us]
      - CPU utilization in user mode (min, max, avg) [%]
      - CPU utilization in system mode (min, max, avg) [%]
      - Total CPU utilization (min, max, avg) [%]
      - Resident set size (min, max, avg) [MiB]
      - NVIDIA GPU utilization
      - NVIDIA GPU memory

    Planned statistics:
      - AMD GPU utilization
      - AMD GPU memory

    TODO:
      - Windows support
    """

    def __init__(self, uid, nw, rinterv, subsamp):
        """
        Constructor.

        Arguments:

          uid: The unique ID of the SPITZ process, used when creting the
          statistics file in ./perf/<UID>-suffix.

          nw: The number of compute workers in the CPU, this is printed in
          the logs and it is not used to normalize any of the statistics.

          rinterv: The report interval, in seconds. Must be an integer greater
          than 1.

          subsamp: The number of steps in between report intervals to acquire
          statistics.
        """

        self.stop = False
        self.uid = uid
        self.nw = nw
        self.rinterv = rinterv
        self.subsamp = subsamp

        logging.info('Starting PerfModule...')

        # CPU thread

        def runcpu_wrapper():
            self.RunCPU()

        tcpu = threading.Thread(target=runcpu_wrapper)

        try:
            tcpu.daemon = True
        except:
            pass

        try:
            tcpu.setDaemon(True)
        except:
            pass

        tcpu.start()

        # NV thread

        # Initialize NVML

        try:
            nvmlInit()
        except:
            logging.info('PerfModule: Could not initialize NVML!')
            try:
                _, error, _ = sys.exc_info()
                log_lines(str(error), logging.debug)
                log_lines(traceback.format_exc(), logging.debug)
            except:
                logging.debug('Cannot format exception!')
            return

        # List the GPUs in the system

        try:
            ngpus = 0
            ngpus = nvmlDeviceGetCount()
        except:
            logging.info('PerfModule: Could not enumerate GPU devices!')
            try:
                _, error, _ = sys.exc_info()
                log_lines(str(error), logging.debug)
                log_lines(traceback.format_exc(), logging.debug)
            except:
                logging.debug('Cannot format exception!')

        # Start the NVML threads

        for i in range(ngpus):
            try:
                handle = nvmlDeviceGetHandleByIndex(i)
            except:
                logging.info('PerfModule: Failed to access GPU %d!' % i)
                try:
                    _, error, _ = sys.exc_info()
                    log_lines(str(error), logging.debug)
                    log_lines(traceback.format_exc(), logging.debug)
                except:
                    logging.debug('Cannot format exception!')
                continue

            def runnv_wrapper():
                self.RunNV(i, handle)

            tnv = threading.Thread(target=runnv_wrapper)

            try:
                tnv.daemon = True
            except:
                pass

            try:
                tnv.setDaemon(True)
            except:
                pass

            tnv.start()

    def Stop(self):
        """
        Signal the stop of the monitoring thread. This is often not necessary
        because the monitoring thread is created as a daemon
        """
        self.stop = True

    def Dump(self, header, fields, tag, new):
        """
        Print the fields to the perf file.

        Arguments:

          header: The header describing fields, it is only written when
          the file is initialized.

          fields: The statistics collected. They will be trivially converted to
          string before writing, if any formatting is needed, the field must be
          previously formatted and passed as string.

          new: Create a new file (or truncate an existing one) and write the
          header before writing the fields if True, otherwise just append
          fields.
        """
        dirname = './perf/'
        filename = '%s%s-%s' % (dirname, self.uid, tag)
        mode = 'wt' if new else 'at'
        fields = ' '.join([str(i) for i in fields])

        try:
            os.mkdir(dirname)
        except:
            pass

        try:
            with open(filename, mode) as f:
                if new:
                    f.write(header + '\n')
                f.write(fields + '\n')
        except:
            pass

    def Stat(self, pid):
        """
        Query /proc/PID/stat.

        Arguments:

          pid: The target process id.

        Return:

          A tuple with the raw RSS, user time and system time.

        Note:

          This method will throw exception on failure.
        """

        with open('/proc/%d/stat' % pid, 'rt') as f:
            l = f.read()

        # Remove the process name

        i = l.find('(')
        j = l.rfind(')')

        if i >= 0 and j >= 0:
            l = l[:i] + l[j:]

        l = l.split()

        rss = float(l[23])
        ut = float(l[13])
        st = float(l[14])

        return (rss, ut, st)

    def NVStat(self, handle, pid):
        """
        Query information about a GPU.

        Arguments:

          pid: The target process id.
          handle: The NVML handle for the device.

        Return:

          A tuple with the utilization, temperature, sm clock, memory clock,
          total used memory, used memory by the specified PID, power
          consumption and throttling reasons.

        Note:

          Values not supported will be filled with N/A.
        """

        error = -1.0

        try:
            util = nvmlDeviceGetUtilizationRates(handle)
            ut = util.gpu
            mut = util.memory
        except:
            ut = error
            mut = error

        try:
            temp = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
        except:
            temp = error

        try:
            smclk = nvmlDeviceGetClockInfo(handle, NVML_CLOCK_GRAPHICS)
        except:
            smclk = error

        try:
            memclk = nvmlDeviceGetClockInfo(handle, NVML_CLOCK_MEM)
        except:
            memclk = error

        try:
            meminfo = nvmlDeviceGetMemoryInfo(handle)
            mem = meminfo.used / 1024.0 / 1024.0
        except:
            mem = error

        try:
            pmem = error
            for proc in nvmlDeviceGetComputeRunningProcesses(handle):
                if proc.pid == pid and not proc.usedGpuMemory is None:
                    pmem = proc.usedGpuMemory / 1024.0 / 1024.0
        except:
            pass

        try:
            throttle = nvmlDeviceGetCurrentClocksThrottleReasons(handle)
        except:
            throttle = error

        try:
            power = nvmlDeviceGetPowerUsage(handle) / 1000.0
        except:
            power = error

        return (ut, mut, temp, smclk, memclk, mem, pmem, power, throttle)


    def RunCPU(self):
        """
        CPU Monitoring thread.
        """

        # Compute the sleep delay

        delay = float(self.rinterv) / self.subsamp

        # Determine page size

        pagesize = 0

        for pagename in ['SC_PAGESIZE', 'SC_PAGE_SIZE']:
            try:
                pagesize = os.sysconf(pagename)
                break
            except:
                pass

        if pagesize == 0:
            logging.info('PerfModule: Could not determine page size!')
            return

        logging.debug('PerfModule: Page size is %d bytes.' % pagesize)

        # Determine ticks per second

        try:
            ticpersec = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
        except:
            logging.info('PerfModule: Could not determine tick frequency!')
            return

        logging.debug('PerfModule: Tick frequency is %d Hz.' % ticpersec)

        # Get the process PID

        pid = os.getpid()

        # Run the perf module

        logging.info('PerfModule CPU thread started.')

        isnew = True

        refwtime = 0

        lastwtime = 0
        lastutime = 0
        laststime = 0

        while not self.stop:

            minupct = 0
            maxupct = 0
            avgupct = 0

            minspct = 0
            maxspct = 0
            avgspct = 0

            mintpct = 0
            maxtpct = 0
            avgtpct = 0

            minrss = 0
            maxrss = 0
            avgrss = 0

            firstwtime = 0
            firstutime = 0
            firststime = 0

            n = 0

            cpuheader = """# (1) Number of compute workers
# (2) Total wall time (since beginning of PerfModule) [us]
# (3) Total user time (since beginning of PerfModule) [us]
# (4) Total system time (since beginning of PerfModule) [us]
# (5-7) CPU utilization in user mode (min, max, avg) [%]
# (8-10) CPU utilization in system mode (min, max, avg) [%]
# (11-13) Total user + system CPU utilization (min, max, avg) [%]"""

            memheader = """# (1) Total wall time (since beginning of PerfModule) [us]
# (2-4) Resident set size (min, max, avg) [MiB]"""

            for sample in range(self.subsamp):

                if self.stop:
                    break

                try:

                    wt = timeit.default_timer()
                    rss, ut, st = self.Stat(pid)

                    rss = rss * pagesize / 1024.0 / 1024.0
                    ut = ut / ticpersec
                    st = st / ticpersec

                    if refwtime == 0:

                        refwtime = wt
                        delta = delay

                        refstamp = datetime.datetime.utcnow()
                        cpuheader = '# ' + \
                            refstamp.strftime('%Y-%m-%d %H:%M:%S.%f') + \
                            '\n' + cpuheader
                        memheader = '# ' + \
                            refstamp.strftime('%Y-%m-%d %H:%M:%S.%f') + \
                            '\n' + memheader

                    else:

                        delta = wt - lastwtime

                        avgrss += rss

                        upd = ut - lastutime
                        spd = st - laststime
                        tpd = upd + spd

                        upc = (upd * 100 / delta)
                        spc = (spd * 100 / delta)
                        tpc = (tpd * 100 / delta)

                        if n == 0:
                            firstwtime = wt
                            firstutime = ut
                            firststime = st
                            minrss = rss
                            maxrss = rss
                            minupct = upc
                            maxupct = upc
                            minspct = spc
                            maxspct = spc
                            mintpct = tpc
                            maxtpct = tpc
                        else:
                            minrss = min(minrss, rss)
                            maxrss = max(maxrss, rss)
                            minupct = min(minupct, upc)
                            maxupct = max(maxupct, upc)
                            minspct = min(minspct, spc)
                            maxspct = max(maxspct, spc)
                            mintpct = min(mintpct, tpc)
                            maxtpct = max(maxtpct, tpc)

                        n += 1

                    lastwtime = wt
                    lastutime = ut
                    laststime = st

                except:
                    # Ignore errors
                    pass

                time.sleep(delay)

            # Something went wrong
            if n == 0:
                continue

            wtime = int((wt - refwtime) * 1000000)
            utime = int(ut * 1000000)
            stime = int(st * 1000000)

            avgrss /= n
            avgupct = ((ut - firstutime) * 100 / (wt - firstwtime))
            avgspct = ((st - firststime) * 100 / (wt - firstwtime))
            avgtpct = ((ut - firstutime + st - firststime) * 100 / (wt - firstwtime))

            if not self.stop:
                self.Dump(cpuheader, [self.nw, wtime, utime, stime, minupct,
                    maxupct, avgupct, minspct, maxspct, avgspct, mintpct,
                    maxtpct, avgtpct], 'cpu', isnew)
                self.Dump(memheader, [wtime, minrss, maxrss, avgrss], 'cpumem', isnew)
                isnew = False

        logging.info('PerfModule CPU thread stopped.')

    def RunNV(self, igpu, handle):
        """
        NVIDIA GPU Monitoring thread
        """

        # Compute the sleep delay

        delay = float(self.rinterv) / self.subsamp

        # Load the basic information about the GPU

        try:
            name = nvmlDeviceGetName(handle).decode('utf8')
        except:
            name = "Unknown"
            logging.info('PerfModule: Could not access GPU name!')
            try:
                _, error, _ = sys.exc_info()
                log_lines(str(error), logging.debug)
                log_lines(traceback.format_exc(), logging.debug)
            except:
                logging.debug('Cannot format exception!')

        try:
            brand = nvmlDeviceGetBrand(handle)
        except:
            brand = NVML_BRAND_UNKNOWN
            logging.info('PerfModule: Could not access GPU brand!')
            try:
                _, error, _ = sys.exc_info()
                log_lines(str(error), logging.debug)
                log_lines(traceback.format_exc(), logging.debug)
            except:
                logging.debug('Cannot format exception!')

        brandNames = {
            NVML_BRAND_UNKNOWN : "Unknown",
            NVML_BRAND_QUADRO  : "Quadro",
            NVML_BRAND_TESLA   : "Tesla",
            NVML_BRAND_NVS     : "NVS",
            NVML_BRAND_GRID    : "Grid",
            NVML_BRAND_GEFORCE : "GeForce",
        }

        fullname = '%s %s' % (brandNames[brand], name)

        try:
            vdriver = nvmlSystemGetDriverVersion().decode('utf8')
        except:
            vdriver = 'N/A'

        try:
            meminfo = nvmlDeviceGetMemoryInfo(handle)
            memtotal = str(meminfo.total / 1024 / 1024) + ' MiB'
        except:
            memtotal = 'N/A'

        try:
            meminfo = nvmlDeviceGetMemoryInfo(handle)
            memtotal = str(meminfo.total / 1024 / 1024) + ' MiB'
        except:
            memtotal = 'N/A'

        try:
            powerlim = nvmlDeviceGetPowerManagementLimit(handle)
            powerlim = str(powerlim / 1000.0) + ' W'
        except:
            powerlim = 'N/A'

        # Get the process PID

        pid = os.getpid()

        # Run the perf module

        logging.info('PerfModule NV thread started.')

        isnew = True

        refwtime = 0
        lastwtime = 0

        while not self.stop:

            minut = 0
            maxut = 0
            avgut = 0

            minmut = 0
            maxmut = 0
            avgmut = 0

            mintemp = 0
            maxtemp = 0
            avgtemp = 0

            minsmclk = 0
            maxsmclk = 0
            avgsmclk = 0

            minmemclk = 0
            maxmemclk = 0
            avgmemclk = 0

            minmem = 0
            maxmem = 0
            avgmem = 0

            minpmem = 0
            maxpmem = 0
            avgpmem = 0

            minpower = 0
            maxpower = 0
            avgpower = 0

            throtbits = 0

            n = 0

            gpuheader = """# (1) Total wall time (since beginning of PerfModule) [us]
# (2-4) Utilization (min, max, avg) [%]
# (5-7) Temperature (min, max, avg) [oC]
# (8-10) SM Clock (min, max, avg) [MHz]
# (11-13) Memory Clock (min, max, avg) [MHz]
# (14-16) Power Consumption (min, max, avg) [W]
# (17) Throttling Reason (accumulated during period)"""

            memheader = """# (1) Total wall time (since beginning of PerfModule) [us]
# (2-4) Total used memory (min, max, avg) [MiB]
# (5-7) Memory used by current PID (min, max, avg) [MiB]
# (8-10) Memory controller utilization (min, max, avg) [%]"""

            for sample in range(self.subsamp):

                if self.stop:
                    break

                try:

                    wt = timeit.default_timer()
                    ut, mut, temp, smclk, memclk, mem, pmem, power, \
                        throttle = self.NVStat(handle, pid)

                    if refwtime == 0:

                        refwtime = wt
                        delta = delay

                        refstamp = datetime.datetime.utcnow()
                        cpuheader = '# ' + \
                            refstamp.strftime('%Y-%m-%d %H:%M:%S.%f') + \
                            '\n# ' + fullname + '\n# Driver version: ' + vdriver + \
                            '\n# Power limit: ' + powerlim + ' [W]\n' + gpuheader
                        memheader = '# ' + \
                            refstamp.strftime('%Y-%m-%d %H:%M:%S.%f') + \
                            '\n# ' + fullname + '\n# ' + memtotal + '\n' + memheader

                    else:

                        delta = wt - lastwtime

                        avgut += ut
                        avgmut += mut
                        avgtemp += temp
                        avgsmclk += smclk
                        avgmemclk += memclk
                        avgmem += mem
                        avgpmem += pmem
                        avgpower += power

                        throtbits = throtbits | throttle

                        if n == 0:
                            minut = ut
                            maxut = ut
                            minmut = mut
                            maxmut = mut
                            mintemp = temp
                            maxtemp = temp
                            minsmclk = smclk
                            maxsmclk = smclk
                            minmemclk = memclk
                            maxmemclk = memclk
                            minmem = mem
                            maxmem = mem
                            minpmem = pmem
                            maxpmem = pmem
                            minpower = power
                            maxpower = power
                        else:
                            minut = min(minut, ut)
                            maxut = max(maxut, ut)
                            minmut = min(minmut, mut)
                            maxmut = max(maxmut, mut)
                            mintemp = min(mintemp, temp)
                            maxtemp = max(maxtemp, temp)
                            minsmclk = min(minsmclk, smclk)
                            maxsmclk = max(maxsmclk, smclk)
                            minmemclk = min(minmemclk, memclk)
                            maxmemclk = max(maxmemclk, memclk)
                            minmem = min(minmem, mem)
                            maxmem = max(maxmem, mem)
                            minpmem = min(minpmem, pmem)
                            maxpmem = max(maxpmem, pmem)
                            minpower = min(minpower, power)
                            maxpower = max(maxpower, power)

                        n += 1

                    lastwtime = wt

                except:
                    # Ignore errors
                    pass

                time.sleep(delay)

            # Something went wrong
            if n == 0:
                continue

            wtime = int((wt - refwtime) * 1000000)

            avgut /= float(n)
            avgmut /= float(n)
            avgtemp /= float(n)
            avgsmclk /= float(n)
            avgmemclk /= float(n)
            avgmem /= float(n)
            avgpmem /= float(n)
            avgpower /= float(n)

            minut = minut if minut >= 0 else 'N/A'
            minmut = minmut if minmut >= 0 else 'N/A'
            mintemp = mintemp if mintemp >= 0 else 'N/A'
            minsmclk = minsmclk if minsmclk >= 0 else 'N/A'
            minmemclk = minmemclk if minmemclk >= 0 else 'N/A'
            minmem = minmem if minmem >= 0 else 'N/A'
            minpmem = minpmem if minpmem >= 0 else 'N/A'
            minpower = minpower if minpower >= 0 else 'N/A'

            maxut = maxut if maxut >= 0 else 'N/A'
            maxmut = maxmut if maxmut >= 0 else 'N/A'
            maxtemp = maxtemp if maxtemp >= 0 else 'N/A'
            maxsmclk = maxsmclk if maxsmclk >= 0 else 'N/A'
            maxmemclk = maxmemclk if maxmemclk >= 0 else 'N/A'
            maxmem = maxmem if maxmem >= 0 else 'N/A'
            maxpmem = maxpmem if maxpmem >= 0 else 'N/A'
            maxpower = maxpower if maxpower >= 0 else 'N/A'

            avgut = avgut if avgut >= 0 else 'N/A'
            avgmut = avgmut if avgmut >= 0 else 'N/A'
            avgtemp = avgtemp if avgtemp >= 0 else 'N/A'
            avgsmclk = avgsmclk if avgsmclk >= 0 else 'N/A'
            avgmemclk = avgmemclk if avgmemclk >= 0 else 'N/A'
            avgmem = avgmem if avgmem >= 0 else 'N/A'
            avgpmem = avgpmem if avgpmem >= 0 else 'N/A'
            avgpower = avgpower if avgpower >= 0 else 'N/A'

            if not self.stop:
                self.Dump(cpuheader, [wtime, minut, maxut, avgut,
                    mintemp, maxtemp, avgtemp, minsmclk, maxsmclk, avgsmclk,
                    minmemclk, maxmemclk, avgmemclk, minpower, maxpower,
                    avgpower, throtbits],
                    'gpu-%d' % igpu, isnew)
                self.Dump(memheader, [wtime, minmem, maxmem, avgmem, minpmem,
                    maxpmem, avgpmem, minmut, maxmut, avgmut],
                    'gpumem-%d' % igpu, isnew)
                isnew = False

        logging.info('PerfModule NV thread stopped.')
