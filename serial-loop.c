/*
 * serial-loop.c - Serial MIDI loopback speed checker
 *
 * C port of serial-loop.py. Sends continuous SysEx on /dev/serial0
 * and measures throughput / loss over a TX-RX loopback link.
 *
 * Build:
 *   cc -O2 -Wall -Wextra -pthread serial-loop.c -o serial-loop
 *
 * Run:
 *   ./serial-loop            (Ctrl+C to stop)
 *
 * SPDX-License-Identifier: CC0-1.0
 *
 * To the extent possible under law, the author(s) have dedicated all
 * copyright and related and neighboring rights to this software to the
 * public domain worldwide. This software is distributed without any
 * warranty.
 *
 * You should have received a copy of the CC0 Public Domain Dedication
 * along with this software. If not, see <https://creativecommons.org/publicdomain/zero/1.0/>.
 */

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>
#include <sys/select.h>

#define SERIAL_PORT "/dev/serial0"
#define BAUD_RATE B38400

static atomic_int running = 1;
static atomic_ulong bytes_sent = 0;
static atomic_ulong bytes_received = 0;

static double now(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec / 1e9;
}

static void *send_data(void *arg)
{
    int fd = *(int *)arg;
    unsigned char message[258];

    srand((unsigned)time(NULL) ^ (unsigned)getpid());

    message[0] = 0xF0;
    message[257] = 0xF7;

    while (atomic_load(&running)) {
        for (int i = 1; i < 257; i++)
            message[i] = rand() & 0x7F;

        ssize_t n = write(fd, message, sizeof(message));
        if (n > 0)
            atomic_fetch_add(&bytes_sent, (unsigned long)n);
    }
    return NULL;
}

static int ttymidi_is_running(void)
{
    DIR *d = opendir("/proc");
    if (!d)
        return 0;

    struct dirent *e;
    int found = 0;
    while ((e = readdir(d)) != NULL) {
        if (e->d_name[0] < '0' || e->d_name[0] > '9')
            continue;

        char path[64];
        snprintf(path, sizeof(path), "/proc/%s/exe", e->d_name);
        char buf[PATH_MAX];
        ssize_t n = readlink(path, buf, sizeof(buf) - 1);
        if (n < 0) {
            snprintf(path, sizeof(path), "/proc/%s/comm", e->d_name);
            FILE *f = fopen(path, "r");
            if (f) {
                if (fgets(buf, sizeof(buf), f) && strcmp(buf, "ttymidi\n") == 0)
                    found = 1;
                fclose(f);
            }
        } else {
            buf[n] = '\0';
            if (strcmp(buf, "/usr/bin/ttymidi") == 0)
                found = 1;
        }
        if (found)
            break;
    }
    closedir(d);
    return found;
}

static int open_serial(const char *port, speed_t baud)
{
    int fd = open(port, O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (fd < 0) {
        perror("open");
        return -1;
    }

    struct termios tty;
    memset(&tty, 0, sizeof(tty));
    if (tcgetattr(fd, &tty) != 0) {
        perror("tcgetattr");
        close(fd);
        return -1;
    }

    cfsetospeed(&tty, baud);
    cfsetispeed(&tty, baud);
    tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8;
    tty.c_cflag |= (CREAD | CLOCAL);
    tty.c_cflag &= ~(PARENB | CSTOPB | CRTSCTS);
    tty.c_iflag = IGNPAR;
    tty.c_oflag = 0;
    tty.c_lflag = 0;
    tty.c_cc[VMIN] = 0;
    tty.c_cc[VTIME] = 0;

    tcflush(fd, TCIOFLUSH);
    if (tcsetattr(fd, TCSANOW, &tty) != 0) {
        perror("tcsetattr");
        close(fd);
        return -1;
    }
    return fd;
}

static void *read_and_measure(void *arg)
{
    int fd = *(int *)arg;
    unsigned char buf[4096];

    double start_time = now();
    double last_stats_time = start_time;

    while (atomic_load(&running)) {
        fd_set rfds;
        FD_ZERO(&rfds);
        FD_SET(fd, &rfds);

        struct timeval tv = {0, 0};
        if (select(fd + 1, &rfds, NULL, NULL, &tv) > 0 && FD_ISSET(fd, &rfds)) {
            ssize_t n = read(fd, buf, sizeof(buf));
            if (n > 0)
                atomic_fetch_add(&bytes_received, (unsigned long)n);
        }

        double current_time = now();
        if (current_time - last_stats_time >= 1.0) {
            double elapsed_total = current_time - start_time;
            unsigned long sent = atomic_load(&bytes_sent);
            unsigned long received = atomic_load(&bytes_received);

            double send_rate = elapsed_total > 0 ? (sent * 8.0) / elapsed_total : 0;
            double recv_rate = elapsed_total > 0 ? (received * 8.0) / elapsed_total : 0;
            double real_rate = recv_rate * 1.25;

            printf("Sent: %.0f bits/sec (%lu bytes total)\n", send_rate, sent);
            printf("Recv: %.0f bits/sec real:%.0f (%lu bytes total)\n", recv_rate, real_rate, received);
            printf("Loss: %lu bytes\n", sent - received);
            printf("----------------------------------------\n");
            fflush(stdout);

            last_stats_time = current_time;
        }

        usleep(1000);
    }
    return NULL;
}

int main(void)
{
    if (ttymidi_is_running()) {
        fprintf(stderr, "ttymidi is running.\n");
        fprintf(stderr, "Stop it first: systemctl stop ttymidi-rpi.service\n");
        return 1;
    }

    int fd = open_serial(SERIAL_PORT, BAUD_RATE);
    if (fd < 0) {
        fprintf(stderr, "Make sure %s exists and you have permission to access it\n", SERIAL_PORT);
        return 1;
    }

    printf("Opening %s at %d baud...\n", SERIAL_PORT, 38400);
    printf("Serial port opened successfully\n");
    printf("Make sure TX and RX are connected for loopback!\n");
    printf("Press Ctrl+C to stop\n\n");

    pthread_t sender, reader;
    if (pthread_create(&sender, NULL, send_data, &fd) != 0 ||
        pthread_create(&reader, NULL, read_and_measure, &fd) != 0) {
        perror("pthread_create");
        close(fd);
        return 1;
    }

    pthread_join(reader, NULL);
    atomic_store(&running, 0);
    pthread_join(sender, NULL);

    close(fd);
    return 0;
}