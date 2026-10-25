#include <gazebo/gazebo.hh>
#include <gazebo/physics/physics.hh>
#include <gazebo/msgs/msgs.hh>
#include <gazebo/transport/transport.hh>
#include <iostream>

namespace gazebo
{
class JointStatePublisher : public ModelPlugin
{
public:
  void Load(physics::ModelPtr model, sdf::ElementPtr)
  {
    joint = model->GetJoint("brake_joint");

    node.reset(new transport::Node());
    node->Init(model->GetWorld()->Name());

    pos_pub = node->Advertise<gazebo::msgs::Any>("/brake_joint/pos");
    vel_pub = node->Advertise<gazebo::msgs::Any>("/brake_joint/vel");

    update = event::Events::ConnectWorldUpdateBegin(
      std::bind(&JointStatePublisher::OnUpdate, this));

    std::cout << "[JointStatePublisher Loaded]\n";
  }

  void OnUpdate()
  {
    double p = joint->Position(0);
    double v = joint->GetVelocity(0);

    gazebo::msgs::Any msg1;
    msg1.set_type(gazebo::msgs::Any_ValueType_DOUBLE);
    msg1.set_double_value(p);
    pos_pub->Publish(msg1);

    gazebo::msgs::Any msg2;
    msg2.set_type(gazebo::msgs::Any_ValueType_DOUBLE);
    msg2.set_double_value(v);
    vel_pub->Publish(msg2);
  }

private:
  physics::JointPtr joint;
  transport::NodePtr node;
  transport::PublisherPtr pos_pub, vel_pub;
  event::ConnectionPtr update;
};

GZ_REGISTER_MODEL_PLUGIN(JointStatePublisher)
}
