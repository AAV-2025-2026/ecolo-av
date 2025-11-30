#include <gazebo/gazebo.hh>
#include <gazebo/physics/physics.hh>
#include <termios.h>
#include <unistd.h>
#include <fcntl.h>
#include <iostream>

namespace gazebo
{
class BrakeController : public ModelPlugin
{
public:
  void Load(physics::ModelPtr model, sdf::ElementPtr)
  {
    joint = model->GetJoint("brake_joint");

    InitKeyboard();

    target = 0.0;
    Kp = 200;
    Kd = 30;
    prevError = 0;

    update = event::Events::ConnectWorldUpdateBegin(
      std::bind(&BrakeController::OnUpdate, this));

    std::cout << "[BrakeController Loaded]\n";
    std::cout << "Use: a=apply r=release m=mid\n";
  }

  void OnUpdate()
  {
    CheckKey();

    double pos = joint->Position(0);
    double error = target - pos;

    double d = (error - prevError) / 0.001;
    prevError = error;

    double force = Kp*error + Kd*d;

    joint->SetForce(0, force);
  }

  void InitKeyboard()
  {
    termios t;
    tcgetattr(0, &t);
    t.c_lflag &= ~ICANON;
    t.c_lflag &= ~ECHO;
    tcsetattr(0, TCSANOW, &t);
    fcntl(0, F_SETFL, O_NONBLOCK);
  }

  void CheckKey()
  {
    int c = getchar();

    if (c == 'a'){
      target = 0.15;
      std::cout << "APPLY\n";
    }
    if (c == 'r'){
      target = 0.00;
      std::cout << "RELEASE\n";
    }
    if (c == 'm'){
      target = 0.075;
      std::cout << "MID\n";
    }
  }

private:
  physics::JointPtr joint;
  event::ConnectionPtr update;

  double target;
  double Kp, Kd, prevError;
};

GZ_REGISTER_MODEL_PLUGIN(BrakeController)
}
