#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Doc."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

import re
import os
import threading
import serial
import task_queue
import time
import codecs
import traceback

DeviceEchoError=Exception('device without Echo\n')
DeviceReplyError=Exception('device without reply\n')

def _is_echo(a,b):
    for c in a:
        if c not in b:
            return False
    return True

class SerialMonitor:
    """."""
    TERMINATOR = b'\r\n'
    def __init__(self, consumer):
        self._error = False
        self._is_ready = False
        self._is_thread_alive = False
        self._msg_queue = task_queue.TaskQueue(consumer)
        self._upload_queue = task_queue.TaskQueue(self._upload_task)
        self._port = None
        self._baudrate = 115200
        self._ser_init()
        self.support_excmds={
            'ls':self._ls,
            'rm':self._rm,
            'cat':self._cat,
            'touch':self._touch,
        }

    def _ls(self,file):
        self._command('for k,v in pairs(file.list()) do print(k,v) end')

    def _cat(self,file):
        try:
            self._command('=file.open("%s")'%file,rsp='true',echo=False)
            self._command('=file.read()')
            self._command('=file.close()',echo=False)
        except Exception as e:
            self._msg_queue.put('can`t open this file\n')

    def _rm(self,file):
        self._command('=file.remove("%s")'%file,echo=False)
        self._msg_queue.put('\n> ')

    def _touch(self,file):
        self._command('=file.open("%s","w")'%file,rsp='true',echo=False)
        self._command('=file.close()',echo=False)
        self._msg_queue.put('\n> ')

    @property
    def is_ready(self):
        return self._is_ready

    @property
    def port(self):
        return self._port

    @port.setter
    def port(self,p):
        if p != self._port:
            self.stop()
            self.ser.port=p
            self.start()

    @property
    def baudrate(self):
        return self._baudrate

    @baudrate.setter
    def baudrate(self,baud):
        if baud != self._baudrate:
            self.stop()
            self.ser.baudrate=baud
            self.start()

    def _ser_init(self):
        self.ser = serial.Serial()
        self.ser.setDTR(False)
        self.ser.setRTS(False)
        self.ser.port = self._port
        self.ser.baudrate = self._baudrate
        self.ser.timeout=0.3

    def reset_dev(self):
        self._msg_queue.put('Reset dev ...\n')
        self.ser.setRTS(True)  # EN->LOW
        time.sleep(0.1)
        self.ser.setRTS(False)

    def _check_ready(self):
        try:
            # RTS would be LOW changed by serial.open() which cause device restart, 
            # so set DTR be HIGH, avoid device restart, this problem only happen on linux
            self.ser.setDTR(True)
            self.ser.open()
        except serial.SerialException as e:
            if self._port and self._baudrate:
                self._ser_init()
                try:
                    self.ser.open()
                except serial.SerialException as e:
                    raise e
            else:
                raise e
        finally:
            self.ser.setDTR(False)

    def start(self, log=True):
        if not self._is_ready and self.ser.port and self.ser.baudrate:
            try:
                self._check_ready()
            except Exception as e:
                self._msg_queue.put(str(e))
            else:
                self._port=self.ser.port
                self._baudrate=self.ser.baudrate
                self._is_ready = True
                if not self._is_thread_alive:
                    self._lock = threading.Lock()
                    self._start_read_thread()
                if log:
                    self._msg_queue.put('Success connect Port:"%s" Baudrate:%d! Press F1 to Disconnet\n> '%(self._port,self._baudrate))

    def stop(self, log=True):
        if self._is_ready:
            self._is_ready = False
            self._stop_read_thread()
            self.ser.close()
            if log:
                self._msg_queue.put('Disconnect Port:"%s"! Press F1 to Connect\n'%self._port)

    def _start_read_thread(self):
        if not self._is_thread_alive:
            self._is_thread_alive = True
            self.thread = threading.Thread(target=self._run)
            self.thread.daemon = True
            self.thread.start()

    def _stop_read_thread(self):
        if self._is_thread_alive:
            self._is_thread_alive = False
            if hasattr(self.ser, 'cancel_read'):
                self.ser.cancel_read()
            if self.thread and self.thread.isAlive():
                self.thread.join(2)

    def _run(self):
        while self._is_thread_alive:
            try:
                data = self.ser.read( self.ser.in_waiting or 1)
            except serial.SerialException as e:
                self._is_thread_alive=False
                self._is_ready=False
                self._port = None
                self._msg_queue.put(str(e)+'\n')
                break
            else:
                if data:
                    self._msg_queue.put(self.data2str(data))
            if not self._is_thread_alive:
                break
            time.sleep(0.01)

    def data2str(self,data):
        data = data.replace(b'\r', b'').replace(b'\r\n', b'\n').replace(b'\x1b',b'')
        return data.decode('utf-8', 'replace')

    def send(self, text):
        """."""
        if self._is_ready:
            with self._lock:
                m=re.match(r'(\w+)\s*(\S*)',text)
                if m:
                    (op,file)=m.group(1,2)
                    op=self.support_excmds.get(op)
                    if op:
                        self._stop_read_thread()
                        try:
                            op(file)
                        except Exception as e:
                            self._msg_queue.put(str(e))
                        self._start_read_thread()
                    else:
                        self.ser.write(text.encode('utf-8', 'replace')+self.TERMINATOR)
                else:
                    self.ser.write(text.encode('utf-8', 'replace')+self.TERMINATOR)

    def _command(self, cmd, rsp=None, echo=True):
        ser=self.ser
        if ser.in_waiting>0:
            ser.flushInput()
        ser.write(cmd.encode('utf-8', 'replace')+self.TERMINATOR)
        has_echo=False
        has_rsp=False
        buf=bytearray()
        packet=''
        for _ in range(1000):
            data=ser.read(ser.in_waiting or 1)
            buf.extend(data)
            if not data or (b'\n> ' in buf):
                packet=self.data2str(buf)
                del buf
                break;
        if echo:
            self._msg_queue.put(packet)
        if not _is_echo(cmd,packet):
            raise DeviceEchoError
        if rsp and rsp not in packet:
            raise DeviceReplyError

    def _upload_task(self, fp):
        if self._is_ready:
            with self._lock:
                with codecs.open(fp, 'r', 'utf-8') as f:
                    filename=os.path.basename(fp)
                    try:
                        self._stop_read_thread()
                        self._command("file.close()")
                        self._command("=file.open('%s','w')"%filename,'true')
                        line = f.readline()
                        while line != '':
                            if not line.startswith("--"):
                                self._command("file.writeline([==[" + line.strip() + "]==])")
                            line = f.readline()
                        self._command("file.flush()")
                        self._command("file.close()")
                        # self._command("dofile('%s')"%filename)
                    except Exception as e:
                        traceback.print_exc()
                        self._msg_queue.put(str(e))
                    finally:
                        self._start_read_thread()


    def upload(self, fp):
        self._upload_queue.put(fp)