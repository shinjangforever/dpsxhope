// stop_distance.cpp — ระยะหยุดของชั้นป้องกัน เขียนด้วย C++ มาตรฐานล้วน
//
// สูตรเดียวกับ `python hope.py robot stop` (fields/robotics/robokit/stopping.py):
//   ระยะหยุด = ความเร็ว × เวลาตอบสนอง + ความเร็ว² / (2 × อัตราหน่วง)
//   ระยะที่ต้องมี = ระยะหยุด × ตัวคูณเผื่อ
// ใช้เป็นตัวอย่างว่าส่วนที่ต้องรันบนตัวหุ่นยนต์และตอบสนองเร็ว เขียนด้วย C++ ได้อย่างไร
// และให้ผลตรงกับเครื่องมือฝั่ง Python ที่ใช้ตอนออกแบบ
//
// คอมไพล์: g++ -std=c++17 -O2 -Wall -Wextra -o stop_distance stop_distance.cpp
// รัน:     ./stop_distance 0.5 0.2 2.0 0.4        (ความเร็ว เวลาตอบสนอง อัตราหน่วง ระยะที่มี [ตัวคูณเผื่อ])
// รหัสออก: 0 = หยุดทัน, 1 = หยุดไม่ทัน, 2 = ค่าที่ใส่ใช้ไม่ได้
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <string>

struct StopResult {
    double reaction_distance;   // ระยะที่วิ่งไปก่อนเบรกเริ่มทำงาน
    double braking_distance;    // ระยะตอนเบรก
    double stop_distance;       // ผลรวม
    double required;            // ผลรวมคูณตัวเผื่อ
    bool fits;                  // ระยะที่มีพอไหม
};

// ค่าทุกตัวต้องเป็นจำนวนจริงที่จำกัด: NaN และ infinity ถูกปฏิเสธ เพราะการเทียบค่ากับ NaN ให้ผลเป็นเท็จเสมอ
// ถ้าปล่อยผ่าน ด่าน "หยุดทันไหม" จะตอบผิดโดยไม่มีข้อผิดพลาดให้เห็น
StopResult stopping(double speed, double react, double decel, double available, double safety_factor = 1.5) {
    for (double value : {speed, react, decel, available, safety_factor}) {
        if (!std::isfinite(value)) throw std::invalid_argument("ทุกค่าต้องเป็นจำนวนจริงที่จำกัด");
    }
    if (speed < 0 || react < 0 || available < 0) throw std::invalid_argument("ความเร็ว เวลาตอบสนอง และระยะที่มี ต้องไม่ติดลบ");
    if (decel <= 0) throw std::invalid_argument("อัตราหน่วงต้องมากกว่า 0");
    if (safety_factor < 1) throw std::invalid_argument("ตัวคูณเผื่อต้องไม่ต่ำกว่า 1");

    StopResult r{};
    r.reaction_distance = speed * react;
    r.braking_distance = speed * speed / (2.0 * decel);
    r.stop_distance = r.reaction_distance + r.braking_distance;
    r.required = r.stop_distance * safety_factor;
    r.fits = r.required <= available;
    return r;
}

static double parse(const char* text) {
    char* end = nullptr;
    double value = std::strtod(text, &end);
    if (end == text || *end != '\0') throw std::invalid_argument(std::string("ไม่ใช่ตัวเลข: ") + text);
    return value;
}

int main(int argc, char** argv) {
    if (argc < 5 || argc > 6) {
        std::fprintf(stderr, "ใช้: %s ความเร็ว(m/s) เวลาตอบสนอง(s) อัตราหน่วง(m/s2) ระยะที่มี(m) [ตัวคูณเผื่อ]\n", argv[0]);
        return 2;
    }
    try {
        double factor = argc == 6 ? parse(argv[5]) : 1.5;
        StopResult r = stopping(parse(argv[1]), parse(argv[2]), parse(argv[3]), parse(argv[4]), factor);
        // บรรทัดแรกเป็นตัวเลขล้วนคั่นด้วยเว้นวรรค ให้โปรแกรมอื่นอ่านต่อได้
        std::printf("%.6f %.6f %.6f %.6f %d\n", r.reaction_distance, r.braking_distance, r.stop_distance, r.required, r.fits ? 1 : 0);
        std::printf("%s\n", r.fits ? "หยุดทัน" : "หยุดไม่ทัน");
        return r.fits ? 0 : 1;
    } catch (const std::invalid_argument& error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 2;
    }
}
